"""
MQTT Connection Statistics Tracker
Tracks connection events, disconnections, and provides diagnostics
"""
import logging
import time
import threading
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

        # Flood detection and logging
        self.flood_threshold = 100  # messages per minute to trigger flood mode
        self.is_flood_mode = False
        self.last_flood_summary = 0  # timestamp of last flood summary log
        self.flood_summary_interval = 30  # seconds between summary logs during floods

        # Enhanced flood detection - per-node problem tracking
        self.node_problem_counts = {}  # node_id -> problem_type -> count

        # High-volume node detection (2000+ messages/minute)
        self.high_volume_threshold = 2000  # messages per minute to be considered high-volume
        self.node_message_rates = {}  # node_id -> deque of per-minute message counts (last 5 minutes)
        self.node_current_minute_counts = {}  # node_id -> current minute message count
        self.node_minute_start = int(time.time() / 60)  # current minute for node tracking

        # Start background thread for periodic database writes
        self._db_writer_thread = None
        self._stop_db_writer = threading.Event()
        self._start_db_writer_thread()

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
        """Track problems per node for flood detection"""
        if node_id not in self.node_problem_counts:
            self.node_problem_counts[node_id] = {
                'atak_drops': 0,
                'parse_failures': 0,
                'unsupported_types': 0,
                'ignored_channels': 0,
                'processing_errors': 0,
                'raw_messages': 0,
                'last_seen': time.time()
            }

        self.node_problem_counts[node_id][problem_type] += count
        self.node_problem_counts[node_id]['last_seen'] = time.time()

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

                # Get problem counts
                if node_id in self.node_problem_counts:
                    problems = self.node_problem_counts[node_id].copy()
                    node_info['last_seen'] = problems.pop('last_seen', None)
                    node_info['problems'] = problems
                    node_info['total_problems'] = sum(problems.values())

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

                # Include nodes that are problematic (high-volume OR high problem counts)
                is_problematic = (
                    node_info['is_high_volume'] or
                    node_info['total_problems'] >= 50 or  # 50+ problems of any type
                    node_info['problems'].get('atak_drops', 0) >= 10  # 10+ ATAK drops
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

                        # Only write to database if we have significant ATAK activity (1000+ messages)
                        # This avoids cluttering the database with non-flood events
                        if self.atak_messages_current_minute >= 1000:
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

# Global instance
mqtt_stats = MQTTStats()
