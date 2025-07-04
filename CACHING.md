# Caching and Memory Management in MeshInfo-Lite

## Overview

MeshInfo-Lite uses a multi-layered caching system to optimize performance while managing memory usage effectively. The system combines database-level caching, application-level caching, and Flask-Caching to provide fast data access while preventing memory leaks.

## Architecture

### Database Layer
- **MariaDB Query Cache**: Enabled globally with conservative memory settings (~128MB)
- **DatabaseCache Class**: Connection pooling and query result caching
- **Application-Level Cache**: In-memory caching of frequently accessed data

### Application Layer
- **Flask-Caching**: FileSystemCache with configurable timeouts and thresholds
- **MeshData.get_nodes_cached()**: Centralized nodes dictionary caching (60-second TTL)
- **Conditional Feature Loading**: LOS profiles and other heavy features loaded only when needed

### Memory Management
- **Explicit Cleanup**: Manual cleanup of large objects and temporary data
- **Garbage Collection**: Forced GC after memory-intensive operations
- **Memory Monitoring**: Real-time tracking with automatic cleanup triggers

## Key Changes Made

### 1. Database Configuration
- Reduced MariaDB memory allocation from ~512MB to ~128MB
- Enabled query cache globally with appropriate timeout settings
- Removed manual SQL_CACHE hints that caused errors

### 2. Application Caching
- Centralized nodes dictionary caching in `MeshData.get_nodes_cached()`
- Implemented cache timeout configuration from `config.ini`
- Added cache clearing functions for manual cleanup

### 3. Memory Leak Prevention
- Modified `get_node_page_data()` to accept nodes as parameter
- Pass minimal node subsets to `LOSProfile` only when LOS is enabled
- Explicit cleanup of `LOSProfile` instances and temporary data
- Forced garbage collection after node page rendering

### 4. Route Optimization
- Optimized routes to avoid multiple calls to `get_cached_nodes()`
- Created simplified nodes dictionaries with only needed data
- Implemented conditional loading of heavy features

### 5. Monitoring and Debugging
- Added detailed memory usage tracking and analysis
- Implemented cache statistics monitoring
- Created debug endpoints for manual cleanup and analysis
- Added memory watchdog with automatic cleanup triggers

## Configuration

### MariaDB Settings (`custom.cnf`)
```ini
[mysqld]
query_cache_type = 1
query_cache_size = 64M
query_cache_limit = 2M
query_cache_min_res_unit = 4K
```

### Flask-Caching Settings (`config.ini`)
```ini
[server]
app_cache_timeout_seconds = 60
app_cache_max_entries = 100
zero_hop_timeout = 43200
```

## Best Practices

1. **Conservative Memory Settings**: Use minimal memory allocation suitable for small-scale projects
2. **Explicit Cleanup**: Always clean up large objects and temporary data
3. **Conditional Loading**: Load heavy features only when needed
4. **Regular Monitoring**: Monitor memory usage and cache statistics
5. **Graceful Degradation**: Handle cache failures gracefully with fallbacks

## Troubleshooting

### Memory Issues
- Check memory usage with `/api/debug/memory`
- Clear caches with `/api/debug/cleanup`
- Monitor cache statistics with `/api/debug/cache`

### Performance Issues
- Verify database query cache is enabled
- Check application cache hit rates
- Review cache timeout settings

### Database Issues
- Ensure MariaDB is properly configured
- Check connection pool settings
- Verify query cache is working

## Maintenance

- Cache cleanup runs automatically every 15 minutes
- Memory watchdog monitors usage and triggers cleanup when needed
- Debug endpoints available for manual intervention
- Logs provide detailed information about cache and memory usage 