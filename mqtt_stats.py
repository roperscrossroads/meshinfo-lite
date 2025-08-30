"""
MQTT Connection Statistics Tracker
Tracks connection events, disconnections, and provides diagnostics
"""
import logging
import time
import threading
import configparser
from datetime import datetime, timedelta
from collections import deque
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

class MQTTStats:
    def __init__(self):
        self.lock = threading.Lock()

        # Connection tracking
        self.total_connections = 0
        self.total_disconnections = 0
        self.current_connection_start = None
        self.is_connected = False

        # Event history (keep last 100 events)
        self.connection_history = deque(maxlen=100)

        # Message statistics
        self.messages_received = 0
        self.messages_processed = 0
        self.messages_failed = 0
        self.last_message_time = None

        # Message type tracking (portnum statistics)
        self.message_types = {}  # portnum -> count
        self.message_type_names = {}  # portnum -> name
        self.message_types_per_minute = deque(maxlen=60)  # Track types per minute
        self.current_minute_types = {}

        # Performance tracking
        self.uptime_start = time.time()
        self.longest_connection_duration = 0
        self.total_connected_time = 0

        # Recent disconnections with reasons (last 20)
        self.recent_disconnects = deque(maxlen=20)

        # Message rate tracking (per minute)
        self.message_rates = deque(maxlen=60)  # 60 minutes of data
        self.current_minute_messages = 0
        self.current_minute_start = int(time.time() / 60)

        # ATAK flood tracking
        self.atak_messages_current_minute = 0
        self.atak_messages_total = 0
        self.last_db_write_minute = int(time.time() / 60)

        # Raw message tracking
        self.raw_messages_received = 0  # All messages received via MQTT
        self.dropped_messages_total = 0  # Messages dropped (ATAK, failed processing, etc.)

        # Problem aging configuration - time-window based approach
        self.problem_aging_enabled = True
        self.inactive_node_threshold = 24 * 60 * 60  # 24 hours in seconds
        
        # Time windows for different problem types (in seconds)
        # Problems older than these windows are ignored in flood detection
        self.problem_time_windows = {
            'atak_drops': 2 * 60 * 60,      # 2 hours for ATAK drops
            'parse_failures': 4 * 60 * 60,  # 4 hours for parse failures  
            'unsupported_types': 6 * 60 * 60,  # 6 hours for unsupported types
            'ignored_channels': 6 * 60 * 60,   # 6 hours for ignored channels
            'processing_errors': 4 * 60 * 60,  # 4 hours for processing errors
            'raw_messages': 1 * 60 * 60      # 1 hour for raw message tracking
        }
        
        self.last_aging_cleanup = time.time()
        self.aging_cleanup_interval = 15 * 60  # 15 minutes - more frequent cleanup

        # Load configuration for flood detection thresholds
        self._load_flood_config()

        # Flood detection and logging
        self.is_flood_mode = False
        self.last_flood_summary = 0  # timestamp of last flood summary log
        self.flood_summary_interval = 30  # seconds between summary logs during floods

        # Enhanced flood detection - per-node problem tracking with timestamps
        # Structure: node_id -> problem_type -> list of timestamps
        self.node_problem_counts = {}  # node_id -> problem_type -> list of timestamps

        # High-volume node detection (configurable, default 5000+ messages/minute)
        # self.high_volume_threshold is set in _load_flood_config()
        self.node_message_rates = {}  # node_id -> deque of per-minute message counts (last 5 minutes)
        self.node_current_minute_counts = {}  # node_id -> current minute message count
        self.node_minute_start = int(time.time() / 60)  # current minute for node tracking

        # Start background thread for periodic database writes
        self._db_writer_thread = None
        self._stop_db_writer = threading.Event()
        self._start_db_writer_thread()

    def _load_flood_config(self):
        """Load flood detection configuration from config.ini"""
        config = configparser.ConfigParser()
        config.read('config.ini')
        
        # Set default values (updated from original more sensitive thresholds)
        self.flood_threshold = 500  # messages per minute to trigger flood mode (increased from 100)
        self.high_volume_threshold = 5000  # messages per minute to be considered high-volume (increased from 2000)
        self.problem_node_threshold = 100  # total problems to flag a node (increased from 50)
        self.atak_problem_threshold = 50  # ATAK drops to flag a node (increased from 10)
        
        # Override with config file values if present
        if config.has_section('server'):
            try:
                if config.has_option('server', 'flood_threshold'):
                    self.flood_threshold = config.getint('server', 'flood_threshold')
                    logger.info(f"Using configured flood_threshold: {self.flood_threshold}")
                    
                if config.has_option('server', 'high_volume_threshold'):
                    self.high_volume_threshold = config.getint('server', 'high_volume_threshold')
                    logger.info(f"Using configured high_volume_threshold: {self.high_volume_threshold}")
                    
                if config.has_option('server', 'problem_node_threshold'):
                    self.problem_node_threshold = config.getint('server', 'problem_node_threshold')
                    logger.info(f"Using configured problem_node_threshold: {self.problem_node_threshold}")
                    
                if config.has_option('server', 'atak_problem_threshold'):
                    self.atak_problem_threshold = config.getint('server', 'atak_problem_threshold')
                    logger.info(f"Using configured atak_problem_threshold: {self.atak_problem_threshold}")
                
                # Load time window configurations (convert hours to seconds)
                time_window_configs = {
                    'problem_window_atak_drops': 'atak_drops',
                    'problem_window_parse_failures': 'parse_failures',
                    'problem_window_unsupported_types': 'unsupported_types',
                    'problem_window_ignored_channels': 'ignored_channels',
                    'problem_window_processing_errors': 'processing_errors',
                    'problem_window_raw_messages': 'raw_messages'
                }
                
                for config_key, problem_type in time_window_configs.items():
                    if config.has_option('server', config_key):
                        hours = config.getfloat('server', config_key)
                        self.problem_time_windows[problem_type] = int(hours * 60 * 60)
                        logger.info(f"Using configured {config_key}: {hours} hours ({self.problem_time_windows[problem_type]} seconds)")
                    
            except (ValueError, configparser.Error) as e:
                logger.warning(f"Error reading flood detection config, using defaults: {e}")
        
        logger.info(f"Flood detection thresholds: flood={self.flood_threshold}, "
                   f"high_volume={self.high_volume_threshold}, "
                   f"problems={self.problem_node_threshold}, "
                   f"atak_problems={self.atak_problem_threshold}")
        
        logger.info(f"Problem time windows: {', '.join([f'{k}={v/3600:.1f}h' for k, v in self.problem_time_windows.items()])}")

    def on_connect(self, return_code: int):
        """Called when MQTT connects"""
        with self.lock:
            self.total_connections += 1
            self.current_connection_start = time.time()
            self.is_connected = True

            event = {
                'type': 'connect',
                'timestamp': time.time(),
                'return_code': return_code,
                'success': return_code == 0
            }
            self.connection_history.append(event)

            logger.info(f"MQTT Stats: Connection #{self.total_connections}, RC: {return_code}")

    def on_disconnect(self, return_code: int, reason: str = None):
        """Called when MQTT disconnects"""
        with self.lock:
            self.total_disconnections += 1
            disconnect_time = time.time()

            # Calculate connection duration
            if self.current_connection_start:
                duration = disconnect_time - self.current_connection_start
                self.total_connected_time += duration
                if duration > self.longest_connection_duration:
                    self.longest_connection_duration = duration

            self.is_connected = False
            self.current_connection_start = None

            event = {
                'type': 'disconnect',
                'timestamp': disconnect_time,
                'return_code': return_code,
                'reason': reason,
                'duration': duration if self.current_connection_start else 0
            }
            self.connection_history.append(event)
            self.recent_disconnects.append(event)

            logger.warning(f"MQTT Stats: Disconnection #{self.total_disconnections}, RC: {return_code}, Duration: {duration:.1f}s")

    def on_message_received(self, portnum=None, message_type=None):
        """Called when a message is received"""
        with self.lock:
            self.messages_received += 1
            self.last_message_time = time.time()

            # Track message type if provided
            if portnum is not None:
                self.message_types[portnum] = self.message_types.get(portnum, 0) + 1
                if message_type:
                    self.message_type_names[portnum] = message_type

                # NOTE: ATAK counting is now done manually in process_payload.py
                # to ensure we count them even when they're dropped

                # Track per-minute type stats
                current_minute = int(time.time() / 60)
                if current_minute != self.current_minute_start:
                    # Save previous minute's type counts
                    if self.current_minute_types:
                        self.message_types_per_minute.append(self.current_minute_types.copy())
                    self.current_minute_types = {portnum: 1}
                else:
                    self.current_minute_types[portnum] = self.current_minute_types.get(portnum, 0) + 1

            # Update per-minute message rate
            current_minute = int(time.time() / 60)
            if current_minute != self.current_minute_start:
                # New minute, save the previous minute's count
                self.message_rates.append(self.current_minute_messages)

                # Check for flood conditions when minute changes
                self._check_flood_status()

                # Reset counters for new minute
                self.current_minute_messages = 1
                # Note: atak_messages_current_minute is reset manually in process_payload.py
                self.current_minute_start = current_minute
            else:
                self.current_minute_messages += 1

    def on_message_processed(self, success: bool = True):
        """Called when a message is processed"""
        with self.lock:
            if success:
                self.messages_processed += 1
            else:
                self.messages_failed += 1

    def on_raw_message_received(self, node_id=None):
        """Called when any raw MQTT message is received (before processing)"""
        with self.lock:
            self.raw_messages_received += 1

            # Track raw messages per node for high volume detection
            if node_id:
                self.track_node_problem(node_id, 'raw_messages')
                self._track_node_message_rate(node_id)

    def on_message_dropped(self, reason: str = "unknown", node_id=None):
        """Called when a message is dropped (ATAK, failed parsing, etc.)"""
        with self.lock:
            self.dropped_messages_total += 1

            # Handle ATAK-specific counting
            if reason == "ATAK_PLUGIN":
                current_minute = int(time.time() / 60)
                if current_minute != self.current_minute_start:
                    # New minute - reset counter
                    self.atak_messages_current_minute = 1
                    self.current_minute_start = current_minute
                else:
                    self.atak_messages_current_minute += 1

                self.atak_messages_total += 1

            # Track per-node problems if node_id provided
            if node_id:
                problem_map = {
                    "ATAK_PLUGIN": "atak_drops",
                    "UNSUPPORTED_TYPE": "unsupported_types",
                    "IGNORED_CHANNEL": "ignored_channels",
                    "PROCESSING_ERROR": "processing_errors",
                    "PROCESSING_EXCEPTION": "processing_errors"
                }
                if reason in problem_map:
                    self.track_node_problem(node_id, problem_map[reason])

    def track_node_problem(self, node_id, problem_type, count=1):
        """Track problems per node for flood detection using timestamps"""
        current_time = time.time()
        
        if node_id not in self.node_problem_counts:
            self.node_problem_counts[node_id] = {
                'atak_drops': [],
                'parse_failures': [],
                'unsupported_types': [],
                'ignored_channels': [],
                'processing_errors': [],
                'raw_messages': [],
                'last_seen': current_time
            }

        # Add timestamp entries for each occurrence
        for _ in range(count):
            self.node_problem_counts[node_id][problem_type].append(current_time)
        
        self.node_problem_counts[node_id]['last_seen'] = current_time

        # Trigger periodic aging cleanup if enough time has passed
        self._maybe_run_aging_cleanup()

    def _track_node_message_rate(self, node_id):
        """Track per-node message rates for high-volume detection"""
        current_minute = int(time.time() / 60)

        # Initialize node tracking if needed
        if node_id not in self.node_message_rates:
            self.node_message_rates[node_id] = deque(maxlen=5)  # Last 5 minutes
            self.node_current_minute_counts[node_id] = 0

        # Check if we've moved to a new minute
        if current_minute != self.node_minute_start:
            # Save previous minute's counts for all nodes
            for nid in self.node_current_minute_counts:
                if self.node_current_minute_counts[nid] > 0:
                    self.node_message_rates[nid].append(self.node_current_minute_counts[nid])

                    # Check for high-volume activity
                    if self.node_current_minute_counts[nid] >= self.high_volume_threshold:
                        logger.warning(f"High-volume node detected: {nid} sent {self.node_current_minute_counts[nid]} messages in last minute")

            # Reset all node counters for new minute
            for nid in self.node_current_minute_counts:
                self.node_current_minute_counts[nid] = 0

            self.node_minute_start = current_minute

        # Increment current minute counter for this node
        self.node_current_minute_counts[node_id] += 1

    def get_problem_nodes(self):
        """Get list of problematic nodes (high-volume and high-problem counts)"""
        with self.lock:
            problem_nodes = []
            current_time = time.time()

            # Check all nodes that have been tracked
            all_node_ids = set(self.node_problem_counts.keys()) | set(self.node_message_rates.keys())

            for node_id in all_node_ids:
                node_info = {
                    'node_id': node_id,
                    'problems': {},
                    'message_rates': [],
                    'current_minute_rate': 0,
                    'avg_message_rate': 0,
                    'is_high_volume': False,
                    'total_problems': 0,
                    'last_seen': None
                }

                # Get problem counts (only count recent problems within time windows)
                if node_id in self.node_problem_counts:
                    node_data = self.node_problem_counts[node_id]
                    node_info['last_seen'] = node_data.get('last_seen', None)
                    
                    # Count recent problems within their respective time windows
                    recent_problems = {}
                    for problem_type in ['atak_drops', 'parse_failures', 'unsupported_types',
                                       'ignored_channels', 'processing_errors']:
                        count = self._count_recent_problems(node_id, problem_type)
                        if count > 0:  # Only include problem types that have recent occurrences
                            recent_problems[problem_type] = count
                    
                    node_info['problems'] = recent_problems
                    node_info['total_problems'] = sum(recent_problems.values())

                # Get message rate data
                if node_id in self.node_message_rates:
                    rates = list(self.node_message_rates[node_id])
                    node_info['message_rates'] = rates
                    node_info['avg_message_rate'] = sum(rates) / len(rates) if rates else 0

                # Get current minute rate
                if node_id in self.node_current_minute_counts:
                    node_info['current_minute_rate'] = self.node_current_minute_counts[node_id]

                # Determine if high-volume (requires sustained activity, not just single spikes)
                # Count how many recent minutes had high volume
                recent_high_minutes = sum(1 for rate in node_info['message_rates'] if rate >= self.high_volume_threshold)

                node_info['is_high_volume'] = (
                    node_info['current_minute_rate'] >= self.high_volume_threshold or  # Currently flooding
                    recent_high_minutes >= 2 or  # 2+ high-volume minutes in last 5 minutes
                    node_info['avg_message_rate'] >= self.high_volume_threshold  # Sustained average
                )

                # Filter out nodes that haven't been seen recently (only for display)
                current_time = time.time()
                last_seen = node_info.get('last_seen', 0)
                time_since_seen = current_time - last_seen

                # Skip nodes inactive for more than 2 hours for display purposes
                display_inactive_threshold = 2 * 60 * 60  # 2 hours
                if time_since_seen > display_inactive_threshold:
                    continue

                # Include nodes that are problematic (high-volume OR high problem counts)
                is_problematic = (
                    node_info['is_high_volume'] or
                    node_info['total_problems'] >= self.problem_node_threshold or  # Configurable threshold (default 100, increased from 50)
                    node_info['problems'].get('atak_drops', 0) >= self.atak_problem_threshold  # Configurable threshold (default 50, increased from 10)
                )

                if is_problematic:
                    problem_nodes.append(node_info)

            # Sort by severity (high-volume first, then by total problems)
            problem_nodes.sort(key=lambda x: (
                -int(x['is_high_volume']),  # High-volume first
                -x['current_minute_rate'],  # Then by current activity
                -x['total_problems']        # Then by total problems
            ))

            return problem_nodes

    def get_stats(self) -> Dict:
        """Get current statistics"""
        with self.lock:
            current_time = time.time()

            # Current connection duration
            current_connection_duration = 0
            if self.is_connected and self.current_connection_start:
                current_connection_duration = current_time - self.current_connection_start

            # Total uptime
            total_uptime = current_time - self.uptime_start

            # Connection uptime percentage
            total_connected = self.total_connected_time
            if self.is_connected and self.current_connection_start:
                total_connected += current_connection_duration

            uptime_percentage = (total_connected / total_uptime * 100) if total_uptime > 0 else 0

            # Average message rate (messages per minute)
            avg_message_rate = 0
            if self.message_rates:
                avg_message_rate = sum(self.message_rates) / len(self.message_rates)

            # Time since last message
            time_since_last_message = None
            if self.last_message_time:
                time_since_last_message = current_time - self.last_message_time

            # Get top message types
            top_message_types = []
            if self.message_types:
                # Sort by count and get top 10
                sorted_types = sorted(self.message_types.items(), key=lambda x: x[1], reverse=True)[:10]
                for portnum, count in sorted_types:
                    type_name = self.message_type_names.get(portnum, f"Unknown (portnum {portnum})")
                    percentage = (count / self.messages_received * 100) if self.messages_received > 0 else 0

                    # Calculate rate per minute for this type
                    type_rate = 0
                    if self.message_types_per_minute:
                        recent_counts = [m.get(portnum, 0) for m in self.message_types_per_minute]
                        if recent_counts:
                            type_rate = sum(recent_counts) / len(recent_counts)

                    top_message_types.append({
                        'portnum': portnum,
                        'name': type_name,
                        'count': count,
                        'percentage': percentage,
                        'rate_per_minute': type_rate
                    })

            return {
                'connection_status': self.is_connected,
                'total_connections': self.total_connections,
                'total_disconnections': self.total_disconnections,
                'current_connection_duration': current_connection_duration,
                'longest_connection_duration': self.longest_connection_duration,
                'uptime_percentage': uptime_percentage,
                'total_uptime': total_uptime,
                'messages_received': self.messages_received,
                'messages_processed': self.messages_processed,
                'messages_failed': self.messages_failed,
                'message_success_rate': (self.messages_processed / max(1, self.messages_received) * 100),
                'avg_message_rate_per_minute': avg_message_rate,
                'current_minute_messages': self.current_minute_messages,
                'time_since_last_message': time_since_last_message,
                'recent_disconnects': list(self.recent_disconnects),
                'connection_history': list(self.connection_history),
                'top_message_types': top_message_types,
                'message_type_count': len(self.message_types),
                'atak_messages_current_minute': self.atak_messages_current_minute,
                'atak_messages_total': self.atak_messages_total,
                'raw_messages_received': self.raw_messages_received,
                'dropped_messages_total': self.dropped_messages_total
            }

    def get_health_status(self) -> Dict:
        """Get health status for monitoring"""
        stats = self.get_stats()

        # Determine health based on various factors
        issues = []
        health_score = 100

        if not stats['connection_status']:
            issues.append("MQTT disconnected")
            health_score -= 50

        if stats['time_since_last_message'] and stats['time_since_last_message'] > 300:  # 5 minutes
            issues.append("No messages received in 5+ minutes")
            health_score -= 20

        if stats['uptime_percentage'] < 95:
            issues.append(f"Low uptime: {stats['uptime_percentage']:.1f}%")
            health_score -= 15

        if stats['message_success_rate'] < 90:
            issues.append(f"High message failure rate: {100 - stats['message_success_rate']:.1f}%")
            health_score -= 10

        if len(stats['recent_disconnects']) > 10:  # More than 10 disconnects recently
            issues.append("Frequent disconnections detected")
            health_score -= 15

        # Determine status
        if health_score >= 95:
            status = "healthy"
        elif health_score >= 80:
            status = "warning"
        else:
            status = "critical"

        return {
            'status': status,
            'health_score': max(0, health_score),
            'issues': issues,
            'last_updated': time.time()
        }

    def _start_db_writer_thread(self):
        """Start the background thread for writing ATAK flood stats to database"""
        if self._db_writer_thread is None or not self._db_writer_thread.is_alive():
            self._db_writer_thread = threading.Thread(target=self._db_writer_worker, daemon=True)
            self._db_writer_thread.start()
            logger.info("Started ATAK flood stats database writer thread")

    def _db_writer_worker(self):
        """Background worker that periodically writes ATAK flood stats to database"""
        while not self._stop_db_writer.is_set():
            try:
                # Wait for 60 seconds or until stop signal
                if self._stop_db_writer.wait(60):
                    break

                current_minute = int(time.time() / 60)

                # Check if we need to write data for the previous minute
                with self.lock:
                    if current_minute > self.last_db_write_minute:
                        # We have a completed minute to write
                        # Use the ATAK counter that was tracked manually
                        # Note: We write the data from the minute that just completed

                        # Get total message count from the last completed minute
                        recent_minute_data = list(self.message_types_per_minute)[-1] if self.message_types_per_minute else {}
                        total_count = sum(recent_minute_data.values()) if recent_minute_data else self.current_minute_messages

                        # Only write to database if we have significant ATAK activity (configurable threshold, default 2000+)
                        # This avoids cluttering the database with non-flood events
                        atak_db_threshold = getattr(self, 'atak_problem_threshold', 50) * 40  # 40x ATAK problem threshold
                        if self.atak_messages_current_minute >= atak_db_threshold:
                            completed_minute_timestamp = (current_minute - 1) * 60
                            minute_start = datetime.fromtimestamp(completed_minute_timestamp)

                            # Calculate percentage of ATAK messages vs total messages received
                            # total_count already includes all message types except dropped ones
                            # ATAK messages are dropped, so the percentage is ATAK vs total raw messages
                            total_raw_messages = total_count + self.atak_messages_current_minute
                            percentage = (self.atak_messages_current_minute / max(1, total_raw_messages)) * 100

                            # Write to database only for actual flood events
                            self._write_to_database(minute_start, self.atak_messages_current_minute, total_raw_messages, percentage)
                            logger.warning(f"ATAK flood event recorded: {self.atak_messages_current_minute} ATAK messages in one minute")

                        # Update last write minute
                        self.last_db_write_minute = current_minute - 1

            except Exception as e:
                logger.error(f"Error in ATAK flood stats database writer: {e}")

    def _write_to_database(self, minute_period, atak_count, total_count, percentage):
        """Write ATAK flood stats to database"""
        try:
            # Import here to avoid circular imports
            from meshdata import MeshData

            # Get database connection
            mesh_data = MeshData()
            mesh_data.store_atak_flood_stats(minute_period, atak_count, total_count, percentage)

            logger.info(f"Stored ATAK flood stats: {minute_period}, ATAK: {atak_count}/{total_count} ({percentage:.1f}%)")

        except Exception as e:
            logger.error(f"Failed to write ATAK flood stats to database: {e}")

    def _check_flood_status(self):
        """Check if we're in flood conditions and log appropriately"""
        # Calculate current message rate (messages per minute)
        current_rate = self.current_minute_messages

        # Check if we should enter flood mode
        if not self.is_flood_mode and current_rate >= self.flood_threshold:
            self.is_flood_mode = True
            logger.warning(f"Message flood detected: {current_rate} messages/min (threshold: {self.flood_threshold}). Switching to summary logging.")

        # Check if we should exit flood mode
        elif self.is_flood_mode and current_rate < self.flood_threshold * 0.7:  # 70% of threshold to prevent flapping
            self.is_flood_mode = False
            logger.info(f"Message flood ended: {current_rate} messages/min. Resuming normal logging.")

    def should_log_message_reception(self):
        """Determine if individual message reception should be logged"""
        current_time = time.time()

        if not self.is_flood_mode:
            # Normal mode - log all messages at DEBUG level
            return True, "debug"

        # Flood mode - only log summary every 30 seconds
        if current_time - self.last_flood_summary >= self.flood_summary_interval:
            self.last_flood_summary = current_time
            return True, "summary"

        # Flood mode - suppress individual message logs
        return False, None

    def get_flood_summary_message(self):
        """Generate a summary message for flood logging"""
        # Get top message types for summary
        top_types = []
        if self.message_types:
            sorted_types = sorted(self.message_types.items(), key=lambda x: x[1], reverse=True)[:3]
            for portnum, count in sorted_types:
                type_name = self.message_type_names.get(portnum, f"portnum {portnum}")
                percentage = (count / max(1, self.messages_received)) * 100
                top_types.append(f"{type_name} ({percentage:.0f}%)")

        top_types_str = ", ".join(top_types) if top_types else "none"

        return (f"Flood summary: {self.current_minute_messages} msgs/min, "
                f"{self.atak_messages_current_minute} ATAK drops, "
                f"{self.dropped_messages_total} total drops. "
                f"Top types: {top_types_str}")

    def stop_db_writer(self):
        """Stop the database writer thread"""
        if self._db_writer_thread and self._db_writer_thread.is_alive():
            self._stop_db_writer.set()
            self._db_writer_thread.join(timeout=5)
            logger.info("Stopped ATAK flood stats database writer thread")

    def _maybe_run_aging_cleanup(self):
        """Check if it's time to run aging cleanup and do it if so"""
        if not self.problem_aging_enabled:
            return

        current_time = time.time()
        if current_time - self.last_aging_cleanup >= self.aging_cleanup_interval:
            self._age_problem_counters()
            self.last_aging_cleanup = current_time

    def _count_recent_problems(self, node_id, problem_type=None, time_window=None):
        """Count recent problems for a node within a specified time window"""
        if node_id not in self.node_problem_counts:
            return 0
            
        current_time = time.time()
        node_data = self.node_problem_counts[node_id]
        
        if problem_type:
            # Count specific problem type
            if problem_type not in node_data or not isinstance(node_data[problem_type], list):
                return 0
            
            if time_window is None:
                time_window = self.problem_time_windows.get(problem_type, 4 * 60 * 60)
            
            cutoff_time = current_time - time_window
            return len([ts for ts in node_data[problem_type] if ts > cutoff_time])
        else:
            # Count all problem types (excluding raw_messages and last_seen)
            total = 0
            for prob_type in ['atak_drops', 'parse_failures', 'unsupported_types',
                            'ignored_channels', 'processing_errors']:
                if prob_type in node_data and isinstance(node_data[prob_type], list):
                    if time_window is None:
                        window = self.problem_time_windows.get(prob_type, 4 * 60 * 60)
                    else:
                        window = time_window
                    cutoff_time = current_time - window
                    total += len([ts for ts in node_data[prob_type] if ts > cutoff_time])
            return total

    def _age_problem_counters(self):
        """Age out problem counters based on time windows"""
        if not self.problem_aging_enabled:
            return

        current_time = time.time()
        nodes_to_remove = []
        total_entries_removed = 0

        for node_id, node_data in self.node_problem_counts.items():
            last_seen = node_data.get('last_seen', 0)
            time_since_seen = current_time - last_seen

            # Remove nodes that haven't been seen for more than the threshold
            if time_since_seen > self.inactive_node_threshold:
                nodes_to_remove.append(node_id)
                logger.info(f"Removing inactive node {node_id} from problem tracking (last seen {time_since_seen/3600:.1f} hours ago)")
                continue

            # Clean up old problem entries based on time windows
            node_entries_removed = 0
            for problem_type in ['atak_drops', 'parse_failures', 'unsupported_types',
                               'ignored_channels', 'processing_errors', 'raw_messages']:
                if problem_type in node_data and isinstance(node_data[problem_type], list):
                    time_window = self.problem_time_windows.get(problem_type, 4 * 60 * 60)  # default 4 hours
                    cutoff_time = current_time - time_window
                    
                    # Filter out old entries
                    old_length = len(node_data[problem_type])
                    node_data[problem_type] = [ts for ts in node_data[problem_type] if ts > cutoff_time]
                    new_length = len(node_data[problem_type])
                    
                    entries_removed = old_length - new_length
                    node_entries_removed += entries_removed
                    total_entries_removed += entries_removed

            if node_entries_removed > 0:
                logger.debug(f"Aged out {node_entries_removed} old problem entries for node {node_id}")

        # Remove inactive nodes
        for node_id in nodes_to_remove:
            del self.node_problem_counts[node_id]
            # Also remove from message rate tracking
            if node_id in self.node_message_rates:
                del self.node_message_rates[node_id]
            if node_id in self.node_current_minute_counts:
                del self.node_current_minute_counts[node_id]

        if nodes_to_remove:
            logger.info(f"Problem aging cleanup: removed {len(nodes_to_remove)} inactive nodes")
        
        if total_entries_removed > 0:
            logger.info(f"Problem aging cleanup: removed {total_entries_removed} old problem entries across all nodes")
        """Age out problem counters based on time windows"""
        if not self.problem_aging_enabled:
            return

        current_time = time.time()
        nodes_to_remove = []
        total_entries_removed = 0

        for node_id, node_data in self.node_problem_counts.items():
            last_seen = node_data.get('last_seen', 0)
            time_since_seen = current_time - last_seen

            # Remove nodes that haven't been seen for more than the threshold
            if time_since_seen > self.inactive_node_threshold:
                nodes_to_remove.append(node_id)
                logger.info(f"Removing inactive node {node_id} from problem tracking (last seen {time_since_seen/3600:.1f} hours ago)")
                continue

            # Clean up old problem entries based on time windows
            node_entries_removed = 0
            for problem_type in ['atak_drops', 'parse_failures', 'unsupported_types',
                               'ignored_channels', 'processing_errors', 'raw_messages']:
                if problem_type in node_data and isinstance(node_data[problem_type], list):
                    time_window = self.problem_time_windows.get(problem_type, 4 * 60 * 60)  # default 4 hours
                    cutoff_time = current_time - time_window
                    
                    # Filter out old entries
                    old_length = len(node_data[problem_type])
                    node_data[problem_type] = [ts for ts in node_data[problem_type] if ts > cutoff_time]
                    new_length = len(node_data[problem_type])
                    
                    entries_removed = old_length - new_length
                    node_entries_removed += entries_removed
                    total_entries_removed += entries_removed

            if node_entries_removed > 0:
                logger.debug(f"Aged out {node_entries_removed} old problem entries for node {node_id}")

        # Remove inactive nodes
        for node_id in nodes_to_remove:
            del self.node_problem_counts[node_id]
            # Also remove from message rate tracking
            if node_id in self.node_message_rates:
                del self.node_message_rates[node_id]
            if node_id in self.node_current_minute_counts:
                del self.node_current_minute_counts[node_id]

        if nodes_to_remove:
            logger.info(f"Problem aging cleanup: removed {len(nodes_to_remove)} inactive nodes")
        
        if total_entries_removed > 0:
            logger.info(f"Problem aging cleanup: removed {total_entries_removed} old problem entries across all nodes")

    def reset_problem_counters(self, node_id=None):
        """Manually reset problem counters for a node or all nodes"""
        with self.lock:
            if node_id:
                if node_id in self.node_problem_counts:
                    # Reset all counters but preserve last_seen
                    last_seen = self.node_problem_counts[node_id].get('last_seen', time.time())
                    self.node_problem_counts[node_id] = {
                        'atak_drops': [],
                        'parse_failures': [],
                        'unsupported_types': [],
                        'ignored_channels': [],
                        'processing_errors': [],
                        'raw_messages': [],
                        'last_seen': last_seen
                    }
                    logger.info(f"Reset problem counters for node {node_id}")
            else:
                # Reset all nodes
                count = len(self.node_problem_counts)
                self.node_problem_counts.clear()
                logger.info(f"Reset problem counters for all {count} nodes")

    def get_aging_stats(self):
        """Get statistics about the aging system"""
        current_time = time.time()
        
        # Calculate total problem entries across all nodes
        total_problem_entries = 0
        problem_type_counts = {}
        
        for node_id, node_data in self.node_problem_counts.items():
            for problem_type in ['atak_drops', 'parse_failures', 'unsupported_types',
                               'ignored_channels', 'processing_errors', 'raw_messages']:
                if problem_type in node_data and isinstance(node_data[problem_type], list):
                    count = len(node_data[problem_type])
                    total_problem_entries += count
                    problem_type_counts[problem_type] = problem_type_counts.get(problem_type, 0) + count
        
        return {
            'aging_enabled': self.problem_aging_enabled,
            'inactive_threshold_hours': self.inactive_node_threshold / 3600,
            'problem_time_windows_hours': {k: v / 3600 for k, v in self.problem_time_windows.items()},
            'last_cleanup_minutes_ago': (current_time - self.last_aging_cleanup) / 60,
            'cleanup_interval_minutes': self.aging_cleanup_interval / 60,
            'tracked_nodes': len(self.node_problem_counts),
            'total_problem_entries': total_problem_entries,
            'problem_type_counts': problem_type_counts
        }

# Global instance
mqtt_stats = MQTTStats()
