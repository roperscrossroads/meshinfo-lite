# Import all migrations here
from migrations.add_message_reception import migrate as migrate_message_reception
from migrations.add_traceroute_snr import migrate as migrate_traceroute_snr
from migrations.add_traceroute_id import migrate as migrate_traceroute_id
from migrations.add_channel_info import migrate as migrate_channel_info
from migrations.add_traceroute_improvements import migrate as migrate_traceroute_improvements

# List of migrations to run in order
MIGRATIONS = [
    migrate_message_reception,
    migrate_traceroute_snr,
    migrate_traceroute_id,
    migrate_channel_info,
    migrate_traceroute_improvements
]
