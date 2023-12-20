import aiosqlite
from loguru import logger

async def db_start():
    global db
    db = await aiosqlite.connect('new.db')
    await db.execute(
        "CREATE TABLE IF NOT EXISTS PROFILE(user_id TEXT PRIMARY KEY, name TEXT, age TEXT, photo TEXT, number TEXT, description TEXT, location TEXT)")
    await db.commit()
    logger.info('Create table')


async def create_profile(user_id):
    async with db.execute("SELECT 1 FROM profile WHERE user_id = ?", (user_id,)) as cursor:
        user = await cursor.fetchone()
        logger.info(f'{user_id} launched the bot')
        if not user:
            await db.execute("INSERT INTO profile VALUES(?,?,?,?,?,?,?)",
                             (user_id, '', '', '', '', '', ''))
            await db.commit()
            logger.info(f'Add new user in table. Id {user_id}')


async def edit_profile(state, user_id):
    async with state.proxy() as data:
        await db.execute(
            "UPDATE profile SET name = ?, age = ?, photo = ?, number = ?, description = ?, location = ? WHERE user_id = ?",
            (data['name'], data['age'], data['photo'], data['number'], data['description'], data['location'], user_id))
        await db.commit()
        logger.info(f'Data in the database has been updated. User id {user_id}')
