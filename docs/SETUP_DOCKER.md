# MeshInfo-Lite Docker Setup Guide

This guide covers setting up MeshInfo-Lite with Docker Compose. **Database setup is now fully automatic!**

## Prerequisites

- Docker and Docker Compose installed
- Git (to clone the repository)

## Quick Setup

### 1. Clone and Configure

```bash
# Clone the repository
git clone <repository-url>
cd meshinfo-lite

# Copy the sample configuration
cp docker-compose.yml.sample docker-compose.yml
cp config.ini.sample config.ini
```

### 2. Configure Database Settings

Edit your `config.ini` file:

```ini
[database]
host = mariadb
username = meshdata
password = passw0rd
database = meshdata
root_password = passw0rd
```

**Note**: In Docker Compose, the database host is the service name (`mariadb`), not `localhost`.

### 3. Start Docker Services

```bash
# Start the services
docker-compose up -d

# Check that services are running
docker-compose ps
```

**That's it!** The application now automatically sets up database privileges during startup. No manual setup is required.

### 4. Verify Setup

Check that everything is working:

```bash
# Check application logs (you should see automatic database setup messages)
docker-compose logs meshinfo

# Test the application
curl http://localhost:8001/
```

## Automatic Database Setup

**🎉 NEW: Fully Automatic Setup!** As of this version, MeshInfo-Lite automatically handles database privilege setup when the container starts. 

**What happens automatically:**
- ✅ Container waits for database to become available
- ✅ Database privileges are granted automatically (RELOAD, PROCESS)
- ✅ Application starts with full functionality
- ✅ Setup errors are logged but don't prevent startup
- ✅ All database migrations run automatically

**Benefits:**
- **Zero manual setup** - Just `docker-compose up -d` and you're done
- **Resilient startup** - Container starts even if privilege setup fails temporarily
- **Full logging** - All setup steps are logged for troubleshooting
- **Backwards compatible** - Manual setup still works for advanced scenarios

## What Happens During Automatic Startup

When you run `docker-compose up -d`, here's what happens automatically:

### Container Startup Sequence
1. **Database Container Starts** - MariaDB initializes with basic user and database
2. **App Container Starts** - MeshInfo-Lite container begins startup sequence  
3. **Wait for Database** - App waits until database is fully ready
4. **Automatic Privilege Setup** - Grants RELOAD and PROCESS privileges automatically
5. **Database Migrations** - Runs any pending database schema updates
6. **Application Launch** - Starts the web application with full functionality

### What Gets Set Up Automatically
- ✅ **RELOAD Privilege** - For query cache operations and performance optimization
- ✅ **PROCESS Privilege** - For monitoring and debugging capabilities  
- ✅ **Database Migrations** - Schema updates applied automatically
- ✅ **Error Handling** - Setup continues even if some steps fail

### Startup Resilience
- **Non-blocking Setup** - Container starts even if privilege setup fails temporarily
- **Detailed Logging** - All setup steps logged for troubleshooting
- **Graceful Degradation** - App runs with limited functionality until privileges are available
- **Retry Capability** - Can manually re-run setup anytime with `python setup_docker.py`

## Docker Compose Configuration

The typical `docker-compose.yml` includes:

```yaml
services:
  mariadb:
    image: mariadb
    environment:
      MYSQL_ROOT_PASSWORD: passw0rd
      MYSQL_DATABASE: meshdata
      MYSQL_USER: meshdata
      MYSQL_PASSWORD: passw0rd
    volumes:
      - ./mysql_data:/var/lib/mysql
      - ./custom.cnf:/etc/mysql/conf.d/custom.cnf

  meshinfo:
    build: .
    depends_on:
      - mariadb
    volumes:
      - ./config.ini:/app/config.ini
    ports:
      - 8001:8000
```

## Manual Setup (Advanced/Optional)

**Note**: Manual setup is no longer required for normal Docker deployments. The container now automatically handles database privilege setup. However, you can still perform manual setup if needed for advanced configurations or troubleshooting.

### Manual Database Privilege Setup

If you need to manually set up database privileges (e.g., for custom configurations or troubleshooting):

#### Option A: Using Setup Scripts

```bash
# Run the Python setup script manually
python setup_docker.py

# Or run the shell script inside the container
docker-compose exec meshinfo ./docker_setup.sh
```

#### Option B: Direct Database Commands

If you prefer to set up privileges manually:

### 1. Connect to the MariaDB Container

```bash
# Connect to the MariaDB container
docker-compose exec mariadb mysql -u root -p
# Password: passw0rd
```

### 2. Grant Privileges

```sql
-- Grant RELOAD privilege for query cache operations
GRANT RELOAD ON *.* TO 'meshdata'@'%';

-- Grant PROCESS privilege for monitoring
GRANT PROCESS ON *.* TO 'meshdata'@'%';

-- Apply changes
FLUSH PRIVILEGES;
```

### 3. Test Privileges

```sql
-- Test RELOAD privilege
FLUSH QUERY CACHE;

-- Test PROCESS privilege
SHOW PROCESSLIST;
```

## Troubleshooting

### Common Issues

1. **"Database not available"**
   ```bash
   # Check if services are running
   docker-compose ps
   
   # Check MariaDB logs
   docker-compose logs mariadb
   
   # Restart services
   docker-compose restart
   ```

2. **"Access denied for user"**
   - Verify the database credentials in `config.ini`
   - Check that the MariaDB container is fully started
   - Run the setup script again

3. **"Access denied; you need RELOAD privilege"**
   - Run `python setup_docker.py` to grant privileges
   - Or manually grant privileges as shown above

4. **"Cannot connect to database"**
   - Check that the host is set to `mariadb` (not `localhost`)
   - Verify the Docker network is working
   - Check container logs: `docker-compose logs`

### Debug Commands

```bash
# Check container status
docker-compose ps

# View logs
docker-compose logs meshinfo
docker-compose logs mariadb

# Connect to database container
docker-compose exec mariadb mysql -u meshdata -p meshdata

# Check application health
curl http://localhost:8001/api/debug/database-cache
```

## Production Considerations

### Security

- Change default passwords in production
- Use Docker secrets for sensitive data
- Restrict network access to the database container
- Consider using a managed database service

### Performance

- Adjust MariaDB configuration in `custom.cnf`
- Monitor memory usage and adjust container limits
- Use persistent volumes for data storage
- Consider database backups

### Monitoring

- Set up log aggregation
- Monitor container resource usage
- Use health checks for automated monitoring
- Set up alerts for critical issues

## Next Steps

After setup is complete:

1. **Configure MQTT**: Set up your MQTT broker connection
2. **Import Data**: Import existing node data if available
3. **Customize**: Add your logo and customize the interface
4. **Monitor**: Set up monitoring and alerting
5. **Backup**: Configure regular database backups

## Getting Help

- Check the application logs: `docker-compose logs meshinfo`
- Use debug endpoints: `http://localhost:8001/api/debug/`
- Review the main documentation in `CACHING.md`
- Check the general setup guide in `SETUP.md` 