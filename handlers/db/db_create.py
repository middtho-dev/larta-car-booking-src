import asyncio
import asyncpg
from loguru import logger
from os import path
from dotenv import load_dotenv
import os

load_dotenv()

async def check_tables_exist(conn) -> bool:
    tables = ['users', 'cars', 'bookings', 'photos', 'tokens', 'bot_message', 'reviews']
    for table in tables:
        exists = await conn.fetchval(
            "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = $1)",
            table
        )
        if not exists:
            return False
    return True

async def check_types_exist(conn) -> bool:
    types = ['car_status', 'booking_status', 'photo_stage', 'photo_angle']
    for type_name in types:
        exists = await conn.fetchval(
            "SELECT EXISTS (SELECT 1 FROM pg_type WHERE typname = $1)",
            type_name
        )
        if not exists:
            return False
    return True

async def create_database():
    try:
        conn = await asyncpg.connect(
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASS'),
            host=os.getenv('DB_HOST'),
            port=os.getenv('DB_PORT'),
            database='postgres'
        )
        
        db_exists = await conn.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1",
            os.getenv('DB_NAME')
        )
        
        if not db_exists:
            logger.debug(f"Creating database {os.getenv('DB_NAME')}")
            await conn.execute(f"CREATE DATABASE {os.getenv('DB_NAME')}")
        
        await conn.close()
        
        conn = await asyncpg.connect(
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASS'),
            host=os.getenv('DB_HOST'),
            port=os.getenv('DB_PORT'),
            database=os.getenv('DB_NAME')
        )

        tables_exist = await check_tables_exist(conn)
        types_exist = await check_types_exist(conn)

        if not tables_exist or not types_exist:
            logger.debug("Creating tables and types...")
            with open(path.join('docs', 'db.sql'), 'r', encoding='utf-8') as file:
                sql = file.read()
                
            commands = sql.split(';')
            
            for cmd in commands:
                cmd = cmd.strip()
                if cmd:
                    try:
                        await conn.execute(cmd + ';')
                    except asyncpg.exceptions.DuplicateObjectError:
                        pass
                    except Exception as e:
                        logger.error(f"Error executing command: {e}")
                        logger.error(f"Command: {cmd}")
                        raise
                        
            logger.debug("Tables and types created successfully")
        else:
            logger.debug("Database structure is up to date")
            
        await conn.close()
        return True
        
    except Exception as e:
        logger.error(f"Error creating database: {e}")
        return False

if __name__ == "__main__":
    asyncio.run(create_database()) 