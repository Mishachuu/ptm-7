import sqlite3 as sq

from loguru import logger


async def db_start():
    global db, cur
    db = sq.connect('new.db')
    cur = db.cursor()
    logger.info('Create table')
    cur.execute(
        "CREATE TABLE IF NOT EXISTS PROFILE(user_id TEXT PRIMARY KEY,name TEXT, age TEXT, photo TEXT, number TEXT ,description TEXT, location TEXT)")
    db.commit()


async def create_profile(user_id):
    user = cur.execute(
        "SELECT 1 FROM profile WHERE user_id =='{key}'".format(key=user_id)).fetchone()
    logger.info(f'{user_id} launched the bot')
    if not user:
        cur.execute("INSERT INTO profile VALUES(?,?,?,?,?,?,?)",
                    (user_id, '', '', '', '','',''))
        db.commit()
        logger.info(f'Add new user in table. Id {user_id}')


async def edit_profile(state, user_id):
    async with state.proxy() as data:
        cur.execute(
            "UPDATE profile SET name ='{}', age ='{}', photo ='{}', number ='{}', description ='{}', location ='{}' WHERE user_id == '{}'".format(data['name'], data['age'], data['photo'], data['number'], data['description'],data['location'],user_id ))
        logger.info(f'Data in the database has been updated. User id {user_id}')