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
                self.current_minute_messages = 1
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
                'message_type_count': len(self.message_types)
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

# Global instance
mqtt_stats = MQTTStats()
