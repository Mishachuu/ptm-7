import asyncio
import base64
import hashlib
import io
import sys
import uuid

import openai
import requests
from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import Text
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.dispatcher.handler import CancelHandler
from aiogram.dispatcher.middlewares import BaseMiddleware
from aiogram.types import InlineQueryResultArticle, InputTextMessageContent
from aiogram.utils.exceptions import BotBlocked, Throttled
from conf import API_TOKEN_BOT, API_TOKEN_GPT, API_TOKEN_OPENWEATHER, URL
from loguru import logger
from PIL import Image, PngImagePlugin

from kb import ikb, kb, kb_weather
from sqlite import create_profile, db_start, edit_profile

HELP_COMMAND = """
/help - список команд
/start - начать работу с ботом
/gpt - общение с chatGPT
/gen - генерация изображения
/weather - погода
/profile - создать свой профиль
/link - ссылки на создателя
"""

bot = Bot(API_TOKEN_BOT)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)
openai.api_key = API_TOKEN_GPT


class ClientStatesGroup(StatesGroup):
    name = State()
    age = State()
    photo = State()
    number = State()
    description = State()
    location = State()


async def on_sturtup(_):
    await db_start()
    logger.info('Сhatbot launched')


class ThrottlingMiddleware(BaseMiddleware):
    def __init__(self, limit: int = 2):
        super().__init__()
        self.rate_limit = limit

    async def on_process_message(self, message: types.Message, data: dict):
        dp = Dispatcher.get_current()
        try:
            await dp.throttle(key='antiflood_message', rate=self.rate_limit)
        except Throttled as _t:
            raise CancelHandler()

    async def message_throttled(self, message: types.Message, throttled: Throttled):
        delta = throttled.rate - throttled.delta
        if throttled.exceeded_count <= 2:
            await message.reply('Не спеши!')
        await asyncio.sleep(delta)


@dp.message_handler(commands='start')
async def cmd_start(message: types.Message):
    await bot.send_message(chat_id=message.from_user.id, text='Добро пожаловать. Этот бот поможет тебе найти ответ на любой вопрос, а также сможет сгенерировать картинку', reply_markup=kb)
    await bot.send_sticker(chat_id=message.from_user.id, sticker='CAACAgIAAxkBAAEJmwRkpeGW3uaYwvqRt3zlpu7q-GHSEwACLBkAAh7RQElE4DTtGCLf-S8E')
    await create_profile(user_id=message.from_user.id)
    await message.delete()
    logger.info(f"chat id: {message.from_user.id} commands: start")


@dp.message_handler(commands=['help'])
async def cmd_help(message: types.Message):
    await bot.send_message(chat_id=message.from_user.id,
                           text=HELP_COMMAND, reply_markup=kb)
    await message.delete()
    logger.info(f"chat id: {message.from_user.id} commands: help")


@dp.message_handler(Text(equals='Генерация картинки'))
async def info_gen(message: types.Message):
    await bot.send_message(chat_id=message.from_user.id,
                           text='Для генерации картинки необходимо отправить команду "/gen ваш текст". Для лучшей генерации запрос нужно писать на англ')
    await bot.send_sticker(chat_id=message.from_user.id, sticker='CAACAgIAAxkBAAEJmwpkpeG7ErlHQpRbbxp5gUkpOJaHjAACqxUAAruZyEv9Hi1bIvcxXS8E')
    await message.delete()
    logger.info(f"chat id: {message.from_user.id} commands: gen help")


@dp.message_handler(Text(equals='Chat GPT'))
async def info_gen(message: types.Message):
    await bot.send_message(chat_id=message.from_user.id,
                           text='Для общения с Chat GPT необходимо отправить команду "/gpt ваш текст"')
    await bot.send_sticker(chat_id=message.from_user.id, sticker='CAACAgIAAxkBAAEJmwhkpeGtCxUxQKUnTQSUbfgG-HSxCAACxioAAtwxmEtA1ufj1_6VlS8E')
    await message.delete()
    logger.info(f"chat id: {message.from_user.id} commands: gpt")


@dp.message_handler(Text(equals='Привет'))
async def info_gen(message: types.Message):
    await bot.send_message(chat_id=message.from_user.id,
                           text='Здравстуй. Для получения информации напиши команду "/help"')
    await bot.send_sticker(chat_id=message.from_user.id, sticker='CAACAgIAAxkBAAEJmwZkpeGgjk2_YXVNE3njxXp37Ps37AAC4RUAAiMcQUu72JdRoVaS3i8E')
    await message.delete()
    logger.info(f"chat id: {message.from_user.id} commands: hello")


@dp.message_handler(commands=['gpt'])
async def cmd_gpt(message: types.Message):
    user_text = message.text.split('/gpt', 1)
    if len(user_text) > 1:
        user_text = user_text[1].strip()
    else:
        await bot.send_message(chat_id=message.from_user.id, text='Для генерации ответа от GPT необходимо отправить "/gpt ваш запрос"')
        return
    response = openai.Completion.create(
        engine="text-davinci-002",
        prompt=user_text,
        max_tokens=150,
        stop=None,
    )
    generated_text = response['choices'][0]['text'].strip()
    await bot.send_message(chat_id=message.from_user.id, text=generated_text)
    await message.delete()


@dp.message_handler(commands=['weather'])
async def cmd_weather(message: types.Message):
    await bot.send_message(chat_id=message.from_user.id,
                           text='Для получения данных о погоде необходимо поделиться своим местоположением', reply_markup=kb_weather)
    await message.delete()
    logger.info(f"chat id: {message.from_user.id} commands: weather")


@dp.callback_query_handler(text_contains='location')
async def weather_request(callback: types.CallbackQuery, message: types.Message, state: FSMContext):
    url = f'https://api.openweathermap.org/data/2.5/weather?lat={callback.message.location.latitude}&lon={callback.message.location.longitude}&appid={API_TOKEN_OPENWEATHER}&lang=ru'
    logger.info(f"chat id: {message.from_user.id} commands: location")
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        city = data["name"]
        cur_temp = data["main"]["temp"]
        humidity = data["main"]["humidity"]
        wind = data["wind"]["speed"]
        async with state.proxy() as data:
            data['location'] = message.location
        await callback.message.answer_location(callback.message.location)
        await bot.send_message(chat_id=callback.from_user.id, text=f"Погода в городе: {city}\nТемпература: {cur_temp}°C\n"
                               f"Влажность: {humidity}%\nВетер: {wind} м/с\n")
        logger.info(f"chat id: {callback.from_user.id} location {callback.message.location}")
    except requests.exceptions.RequestException as e:
        await bot.send_message(chat_id=callback.from_user.id, text=f"Ошибка при выполнении запроса: {e}")
        logger.exception(f"Request failed: {e}")
    


@dp.message_handler(commands=['gen'])
async def cmd_gen(message: types.Message):
    logger.info(f"chat id: {message.from_user.id} commands: gen")
    prompt = message.text.split('/gen', 1)[1].strip()
    if len(prompt) > 1:
        prompt = prompt.strip()
    else:
        await bot.send_message(chat_id=message.from_user.id, text='Для генерации картинка вам необходимо отправить <</gen ваш запрос>>')
        logger.warning(f"chat id: {message.from_user.id} Error prompt {prompt}")
        return
    payload = {
        "prompt": prompt,
        "steps": 25,
        "width": 512,
        "height": 512,
        "seed": -1,
        "sampler_index": "DPM++ 2M SDE Karras",
        "negative_prompt": "bad-hands-5", "nsfw"
        "hr_scale": 2
    }
    response = requests.post(url=f'{URL}/sdapi/v1/txt2img', json=payload)
    r = response.json()
    logger.info(f"chat id: {message.from_user.id} response: r")
    for i in r['images']:
        image = Image.open(io.BytesIO(base64.b64decode(i.split(",", 1)[0])))
        png_payload = {
            "image": "data:image/png;base64," + i}
        response2 = requests.post(
            url=f'{URL}/sdapi/v1/png-info', json=png_payload)

        pnginfo = PngImagePlugin.PngInfo()
        pnginfo.add_text("parameters", response2.json().get("info"))
        unique_filename = str(uuid.uuid4()) + ".png"
        image.save(unique_filename, pnginfo=pnginfo)
    with open(unique_filename, 'rb') as photo_file:
        await bot.send_photo(chat_id=message.from_user.id, photo=photo_file)
        logger.info(f"chat id: {message.from_user.id} photo: {photo_file}")


@dp.message_handler(commands=['link'])
async def send_link(message: types.Message):
    await bot.send_sticker(chat_id=message.chat.id, sticker='CAACAgIAAx0Cc1jIOAADSWSgoN65Zo_x2qJVSrL-Frwc_SLcAAIBGQACkgZoSwABgw9FuQABmXkvBA')
    await bot.send_message(chat_id=message.chat.id, text='url', reply_markup=ikb)
    await message.delete()
    logger.info(f"chat id: {message.from_user.id} commands: link")


@dp.inline_handler()
async def inline_echo(inline_query: types.InlineQuery):
    text = inline_query.query or 'Echo'
    input_content = InputTextMessageContent(text)
    result_id = hashlib.md5(text.encode()).hexdigest()
    item = InlineQueryResultArticle(
        input_message_content=input_content, id=result_id, title='Echo!!', description='Check echo', thumb_url='https://avatars.dzeninfra.ru/get-zen_doc/34175/pub_5cea2361585c2f00b5c9cb0b_5cea310a752e5b00b25b9c01/scale_1200')
    await bot.answer_inline_query(inline_query_id=inline_query.id, results=[item])
    logger.info(f"chat id: {result_id} commands: link")



@dp.message_handler(commands=['profile'])
async def profile_name(message: types.Message):
    await ClientStatesGroup.name.set()
    await message.answer('Как тебя зовут?')
    logger.info(f"chat id: {message.from_user.id} commands: profile")



@dp.message_handler(lambda message: message.text.isdigit(), state=ClientStatesGroup.name)
async def check_name(message: types.Message):
    await message.reply('Введите имя!')


@dp.message_handler(lambda message: message, state=ClientStatesGroup.name)
async def profile_name_add(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['name'] = message.text
    await ClientStatesGroup.next()
    await message.reply('А теперь сколько тебе лет?')


@dp.message_handler(lambda message: not message.text.isdigit(), state=ClientStatesGroup.age)
async def check_age(message: types.Message):
    await message.reply('Введите возраст!')


@dp.message_handler(lambda message: message, state=ClientStatesGroup.age)
async def profile_age_add(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['age'] = message.text
    await ClientStatesGroup.next()
    await message.reply('Отправь свое фото')


@dp.message_handler(lambda message: not message.photo, state=ClientStatesGroup.photo)
async def check_photo(message: types.Message):
    await message.reply('ЭТО НЕ ФОТО!')
    logger.error(f"chat id: {message.from_user.id} commands: profile. Not a photo")


@dp.message_handler(lambda message: message.photo, content_types=['photo'], state=ClientStatesGroup.photo)
async def profile_photo_add(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['photo'] = message.photo[0].file_id
    message.photo[0].download
    await message.reply('Фото добавленно')
    await ClientStatesGroup.next()
    await message.answer('Теперь введите ваш номер телефона')


@dp.message_handler(lambda message: message, state=ClientStatesGroup.number)
async def profile_number_add(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['number'] = message.text
    await message.reply('Номер добавлен')
    await ClientStatesGroup.next()
    await message.answer('Теперь введите ваше описание!')


@dp.message_handler(state=ClientStatesGroup.description)
async def profile_description_add(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['description'] = message.text
    await message.reply('Текст добавлен')
    async with state.proxy() as data:
        await bot.send_photo(chat_id=message.from_user.id, photo=data['photo'], caption=f"name: {data['name']} age: {data['age']} number: {data['number']} description: {data['description']}", reply_markup=kb)
    await edit_profile(state, user_id=message.from_user.id)
    await state.finish()
    logger.info(f"chat id: {message.from_user.id}  name: {data['name']} age: {data['age']} number: {data['number']} description: {data['description']}")



@dp.message_handler()
async def info_gen(message: types.Message):
    await bot.send_message(chat_id=message.from_user.id,
                           text='Для работы с ботом используй команды!')
    await bot.send_sticker(chat_id=message.from_user.id, sticker='CAACAgIAAxkBAAEJmwRkpeGW3uaYwvqRt3zlpu7q-GHSEwACLBkAAh7RQElE4DTtGCLf-S8E')
    await message.delete()
    


@dp.errors_handler(exception=BotBlocked)
async def error_bot_blocked(update: types.Update, exception: BotBlocked):
    logger.error('Сhatbot is blocked. id {}')
    return True

if __name__ == '__main__':
    logger.add(sys.stdout, format="{time} - {level} - {message}", filter="sub.module",level='INFO')
    dp.middleware.setup(ThrottlingMiddleware())
    executor.start_polling(dp, on_startup=on_sturtup, skip_updates=True)