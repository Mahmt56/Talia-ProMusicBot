import os
import json
import ffmpeg
import aiohttp
import aiofiles
import asyncio
import requests
import converter
from os import path
from asyncio.queues import QueueEmpty
from pyrogram import Client, filters
from typing import Callable
from helpers.channelmusic import get_chat_id
from callsmusic import callsmusic
from callsmusic.queues import queues
from helpers.admins import get_administrators
from youtube_search import YoutubeSearch
from callsmusic.callsmusic import client as USER
from pyrogram.errors import UserAlreadyParticipant
from downloaders import youtube

from config import que, THUMB_IMG, DURATION_LIMIT, BOT_USERNAME, BOT_NAME, UPDATES_CHANNEL, GROUP_SUPPORT, ASSISTANT_NAME
from helpers.filters import command, other_filters
from helpers.decorators import authorized_users_only
from helpers.gets import get_file_name, get_url
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, Voice
from cache.admins import admins as a
from PIL import Image, ImageFont, ImageDraw

aiohttpsession = aiohttp.ClientSession()
chat_id = None
DISABLED_GROUPS = []
useer ="NaN"


def cb_admin_check(func: Callable) -> Callable:
    async def decorator(client, cb):
        admemes = a.get(cb.message.chat.id)
        if cb.from_user.id in admemes:
            return await func(client, cb)
        else:
            await cb.answer("Bunu yapmana izin verilmiyor.!", show_alert=True)
            return
    return decorator                                                                       
                                          
                                                                                    
def transcode(filename):
    ffmpeg.input(filename).output(
        "input.raw",
        format="s16le",
        acodec="pcm_s16le",
        ac=2,
        ar="48k"
    ).overwrite_output().run() 
    os.remove(filename)

# Convert seconds to mm:ss
def convert_seconds(seconds):
    seconds = seconds % (24 * 3600)
    seconds %= 3600
    minutes = seconds // 60
    seconds %= 60
    return "%02d:%02d" % (minutes, seconds)


# Convert hh:mm:ss to seconds
def time_to_seconds(time):
    stringt = str(time)
    return sum(int(x) * 60 ** i for i, x in enumerate(reversed(stringt.split(":"))))


# Change image size
def changeImageSize(maxWidth, maxHeight, image):
    widthRatio = maxWidth / image.size[0]
    heightRatio = maxHeight / image.size[1]
    newWidth = int(widthRatio * image.size[0])
    newHeight = int(heightRatio * image.size[1])
    newImage = image.resize((newWidth, newHeight))
    return newImage


async def generate_cover(requested_by, title, views, duration, thumbnail):
    async with aiohttp.ClientSession() as session:
        async with session.get(thumbnail) as resp:
            if resp.status == 200:
                f = await aiofiles.open("background.png", mode="wb")
                await f.write(await resp.read())
                await f.close()
    image1 = Image.open("./background.png")
    image2 = Image.open("etc/foreground.png")
    image3 = changeImageSize(1280, 720, image1)
    image4 = changeImageSize(1280, 720, image2)
    image5 = image3.convert("RGBA")
    image6 = image4.convert("RGBA")
    Image.alpha_composite(image5, image6).save("temp.png")
    img = Image.open("temp.png")
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype("etc/font.otf", 60)
    draw.text((40, 550), f"Oynat??l??yor....", (0, 0, 0), font=font)
    draw.text((40, 630),
        f"{title}",
        (0, 0, 0),
        font=font,
    )
    img.save("final.png")
    os.remove("temp.png")
    os.remove("background.png")


@Client.on_message(command(["playlist", f"playlist@Efsanestar_bot"]) & filters.group & ~filters.edited)
async def playlist(client, message):
    global que
    if message.chat.id in DISABLED_GROUPS:
        return
    queue = que.get(message.chat.id)
    if not queue:
        await message.reply_text("**Ak????ta hi??bir ??ey yok!**")
    temp = []
    for t in queue:
        temp.append(t)
    now_playing = temp[0][0]
    by = temp[0][1].mention(style="md")
    msg = "**??al??nan ??ark??lar** di {}".format(message.chat.title)
    msg += "\n??? "+ now_playing
    msg += "\n??? ??stek ??zerine "+by
    temp.pop(0)
    if temp:
        msg += "\n\n"
        msg += "**??ark?? S??ras??**"
        for song in temp:
            name = song[0]
            usr = song[1].mention(style="md")
            msg += f"\n??? {name}"
            msg += f"\n??? Atas permintaan {usr}\n"
    await message.reply_text(msg)

# ============================= Settings =========================================
def updated_stats(chat, queue, vol=100):
    if chat.id in callsmusic.pytgcalls.active_calls:
        stats = "Ayarlar **{}**".format(chat.title)
        if len(que) > 0:
            stats += "\n\n"
            stats += "Ses: {}%\n".format(vol)
            stats += "S??rada ??ark??lar: `{}`\n".format(len(que))
            stats += "??ark?? ??alma: **{}**\n".format(queue[0][0])
            stats += "??stek ??zerine: {}".format(queue[0][1].mention)
    else:
        stats = None
    return stats

def r_ply(type_):
    if type_ == "oynat":
        pass
    else:
        pass
    mar = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("???", "son"),
                InlineKeyboardButton("???", "durdur"),
                InlineKeyboardButton("??????", "devam"),
                InlineKeyboardButton("???", "atla")
            ],
            [
                InlineKeyboardButton("???? ??ark?? bilgisi", "playlist"),
            ],
            [       
                InlineKeyboardButton("??? Kapat", "cls")
            ]        
        ]
    )
    return mar


@Client.on_message(command(["player", f"player@Mp3dinleme_Bot"]) & filters.group & ~filters.edited)
@authorized_users_only
async def settings(client, message):
    playing = None
    if message.chat.id in callsmusic.pytgcalls.active_calls:
        playing = True
    queue = que.get(message.chat.id)
    stats = updated_stats(message.chat, queue)
    if stats:
        if playing:
            await message.reply(stats, reply_markup=r_ply("pause"))
            
        else:
            await message.reply(stats, reply_markup=r_ply("play"))
    else:
        await message.reply("**L??tfen ??nce sesli sohbeti a????n.**")


@Client.on_message(
    command("musicplayer") & ~filters.edited & ~filters.bot & ~filters.private
)
@authorized_users_only
async def hfmm(_, message):
    global DISABLED_GROUPS
    try:
        user_id = message.from_user.id
    except:
        return
    if len(message.command) != 2:
        await message.reply_text(
            "**Sadece biliyorum. ** `/m??zik ??alar a????k` **ve** `/M??zik ??alar kapal??`"
        )
        return
    status = message.text.split(None, 1)[1]
    message.chat.id
    if status == "ON" or status == "on" or status == "On":
        lel = await message.reply("`????leme Al??dm...`")
        if not message.chat.id in DISABLED_GROUPS:
            await lel.edit("**M??zik ??alar zaten etkinle??tirildi.**")
            return
        DISABLED_GROUPS.remove(message.chat.id)
        await lel.edit(
            f"??? **M??zik ??alar bu sohbette etkinle??tirildi.** {message.chat.id}"
        )

    elif status == "OFF" or status == "off" or status == "Off":
        lel = await message.reply("`????leniyor...`")
        
        if message.chat.id in DISABLED_GROUPS:
            await lel.edit("**M??zik ??alar zaten devre d??????.**")
            return
        DISABLED_GROUPS.append(message.chat.id)
        await lel.edit(
            f"??? **M??zik ??alar bu sohbette devre d?????? b??rak??ld??.** {message.chat.id}"
        )
    else:
        await message.reply_text(
            "**Sadece biliyorum.** `/m??zik ??alar a????k` **ve** `/m??zik ??alar kapal??`"
        )


@Client.on_callback_query(filters.regex(pattern=r"^(playlist)$"))
async def p_cb(b, cb):
    global que    
    que.get(cb.message.chat.id)
    type_ = cb.matches[0].group(1)
    cb.message.chat.id
    cb.message.chat
    cb.message.reply_markup.inline_keyboard[1][0].callback_data
    if type_ == "playlist":
        queue = que.get(cb.message.chat.id)
        if not queue:
            await cb.message.edit("**Hi??bir ??ey oynam??yor.???**")
        temp = []
        for t in queue:
            temp.append(t)
        now_playing = temp[0][0]
        by = temp[0][1].mention(style="md")
        msg = "**??imdi y??r??t??len** in {}".format(cb.message.chat.title)
        msg += "\n??? " + now_playing
        msg += "\n??? Taraf??ndan " + by
        temp.pop(0)
        if temp:
            msg += "\n\n"
            msg += "**??ark?? S??ras??**"
            for song in temp:
                name = song[0]
                usr = song[1].mention(style="md")
                msg += f"\n??? {name}"
                msg += f"\n??? Talep eden ki??i {usr}\n"
        await cb.message.edit(msg)      


@Client.on_callback_query(
    filters.regex(pattern=r"^(play|durdur|atla|son|puse|devam|men??|cls)$")
)
@cb_admin_check
async def m_cb(b, cb):
    global que   
    if (
        cb.message.chat.title.startswith("Kanal M??zi??i: ")
        and chat.title[14:].isnumeric()
    ):
        chet_id = int(chat.title[13:])
    else:
        chet_id = cb.message.chat.id
    qeue = que.get(chet_id)
    type_ = cb.matches[0].group(1)
    cb.message.chat.id
    m_chat = cb.message.chat

    the_data = cb.message.reply_markup.inline_keyboard[1][0].callback_data
    if type_ == "durdur":
        if (
            chet_id not in callsmusic.pytgcalls.active_calls
                ) or (
                    callsmusic.pytgcalls.active_calls[chet_id] == "paused"
                ):
            await cb.answer("Asistan sesli sohbete ba??l?? de??il!", show_alert=True)
        else:
            callsmusic.pytgcalls.pause_stream(chet_id)
            
            await cb.answer("M??zik duraklat??ld??!")
            await cb.message.edit(updated_stats(m_chat, qeue), reply_markup=r_ply("play"))
                
    elif type_ == "play":       
        if (
            chet_id not in callsmusic.pytgcalls.active_calls
            ) or (
                callsmusic.pytgcalls.active_calls[chet_id] == "playing"
            ):
                await cb.answer("Asistan sesli sohbete ba??l?? de??il!", show_alert=True)
        else:
            callsmusic.pytgcalls.resume_stream(chet_id)
            await cb.answer("M??zik devam etti!")
            await cb.message.edit(updated_stats(m_chat, qeue), reply_markup=r_ply("pause"))

    elif type_ == "playlist":
        queue = que.get(cb.message.chat.id)
        if not queue:   
            await cb.message.edit("Ak????ta hi??bir ??ey yok!")
        temp = []
        for t in queue:
            temp.append(t)
        now_playing = temp[0][0]
        by = temp[0][1].mention(style="md")
        msg = "**??al??nan ??ark??lar** di {}".format(cb.message.chat.title)
        msg += "\n??? "+ now_playing
        msg += "\n??? ??stek ??zerine "+by
        temp.pop(0)
        if temp:
             msg += "\n\n"
             msg += "**??ark?? S??ras??**"
             for song in temp:
                 name = song[0]
                 usr = song[1].mention(style="md")
                 msg += f"\n??? {name}"
                 msg += f"\n??? ??stek ??zerine {usr}\n"
        await cb.message.edit(msg)      
                      
    elif type_ == "devam":     
        if (
            chet_id not in callsmusic.pytgcalls.active_calls
            ) or (
                callsmusic.pytgcalls.active_calls[chet_id] == "playing"
            ):
                await cb.answer("Sesli sohbet ba??l?? de??il veya zaten oynat??l??yor", show_alert=True)
        else:
            callsmusic.pytgcalls.resume_stream(chet_id)
            await cb.answer("M??zik devam etti!")
     
    elif type_ == "durdur":         
        if (
            chet_id not in callsmusic.pytgcalls.active_calls
                ) or (
                    callsmusic.pytgcalls.active_calls[chet_id] == "paused"
                ):
            await cb.answer("Sesli sohbet ba??l?? de??il veya zaten duraklat??ld??", show_alert=True)
        else:
            callsmusic.pytgcalls.pause_stream(chet_id)
            
            await cb.answer("M??zik duraklat??ld??!")

    elif type_ == "cls":          
        await cb.answer("Men?? kapal??")
        await cb.message.delete()       

    elif type_ == "men??":  
        stats = updated_stats(cb.message.chat, qeue)  
        await cb.answer("Men?? ve Butonlar")
        marr = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("???", "son"),
                    InlineKeyboardButton("???", "durdur"),
                    InlineKeyboardButton("??????", "devam"),
                    InlineKeyboardButton("???", "atla")
                
                ],
                [
                    InlineKeyboardButton("???? ??ark?? bilgisi", "playlist"),
                
                ],
                [       
                    InlineKeyboardButton("??? Kapat", "cls")
                ]        
            ]
        )
        await cb.message.edit(stats, reply_markup=marr)

    elif type_ == "atla":        
        if qeue:
            qeue.pop(0)
        if chet_id not in callsmusic.pytgcalls.active_calls:
            await cb.answer("Asistan sesli sohbete ba??l?? de??il!", show_alert=True)
        else:
            callsmusic.queues.task_done(chet_id)

            if callsmusic.queues.is_empty(chet_id):
                callsmusic.pytgcalls.leave_group_call(chet_id)

                await cb.message.edit("??? No more playlist\n??? Sesli sohbeti b??rakma")
            else:
                callsmusic.pytgcalls.change_stream(
                    chet_id, callsmusic.queues.get(chet_id)["file"]
                )
                await cb.answer("Atlat??ld??")
                await cb.message.edit((m_chat, qeue), reply_markup=r_ply(the_data))
                await cb.message.reply_text(
                    f"??? Atlanan par??a\n??? ??imdi Oynat??l??yor: **{qeue[0][0]}**"
                )

    elif type_ == "son":
        if chet_id in callsmusic.pytgcalls.active_calls:
            try:
                callsmusic.queues.clear(chet_id)
            except QueueEmpty:
                pass

            callsmusic.pytgcalls.leave_group_call(chet_id)
            await cb.message.edit("??? **M??zik durduruldu!**")
        else:
            await cb.answer("Asistan sesli sohbete ba??l?? de??il!", show_alert=True)



@Client.on_message(command("play") & other_filters)
async def play(_, message: Message):
    global que
    global useer
    if message.chat.id in DISABLED_GROUPS:
        return    
    lel = await message.reply("???? **Sesler ????leniyor ????**")
    administrators = await get_administrators(message.chat)
    chid = message.chat.id

    try:
        user = await USER.get_me()
    except:
        user.first_name = "EXProjects"
    usar = user
    wew = usar.id
    try:
        # chatdetails = await USER.get_chat(chid)
        await _.get_chat_member(chid, wew)
    except:
        for administrator in administrators:
            if administrator == message.from_user.id:
                if message.chat.title.startswith("Channel Music: "):
                    await lel.edit(
                        f"<b>Eklemeyi unutmay??n {user.first_name} kanal??n??za</b>",
                    )
                    pass
                try:
                    invitelink = await _.export_chat_invite_link(chid)
                except:
                    await lel.edit(
                        "<b>??nce beni grup y??neticisi olarak ekle</b>",
                    )
                    return

                try:
                    await USER.join_chat(invitelink)
                    await USER.send_message(
                        message.chat.id, "Sesli sohbette bir ??ark?? ??almak i??in kat??ld??m!"
                    )
                    await lel.edit(
                        "<b>yard??mc?? userbot sohbetinize kat??ld??</b>",
                    )

                except UserAlreadyParticipant:
                    pass
                except Exception:
                    # print(e)
                    await lel.edit(
                        f"<b>??? Flood Wait Error! ???\n{user.first_name} userbot i??in kat??lma iste??i nedeniyle grubunuza kat??lam??yor! Kullan??c??lar??n gruplar halinde yasaklanmamas??n?? sa??lama."
                        f"\n\nVeya @Sesmusicasistan grubunuza el ile el ile ve yeniden deneyin</b>",
                    )
    try:
        await USER.get_chat(chid)
        # lmoa = await client.get_chat_member(chid,wew)
    except:
        await lel.edit(
            f"<i>{user.first_name} Bu Grubun yasa????ndan etkilenerek, y??neticiden bir komut g??ndermesini isteyin `/play` ilk kez veya ekleyin @TaliaMusicasistant Elle</i>"
        )
        return
    text_links=None
    await lel.edit("???? **??ark?? ar??yorum..**")
    if message.reply_to_message:
        entities = []
        toxt = message.reply_to_message.text or message.reply_to_message.caption
        if message.reply_to_message.entities:
            entities = message.reply_to_message.entities + entities
        elif message.reply_to_message.caption_entities:
            entities = message.reply_to_message.entities + entities
        urls = [entity for entity in entities if entity.type == 'url']
        text_links = [
            entity for entity in entities if entity.type == 'text_link'
        ]
    else:
        urls=None
    if text_links:
        urls = True
    user_id = message.from_user.id
    user_name = message.from_user.first_name
    rpk = "[" + user_name + "](tg://user?id=" + str(user_id) + ")"
    audio = (
        (message.reply_to_message.audio or message.reply_to_message.voice)
        if message.reply_to_message
        else None
    )
    if audio:
        if round(audio.duration / 60) > DURATION_LIMIT:
            raise DurationLimitError(
                f"**S??resi daha fazla olan ??ark??lar ** `{DURATION_LIMIT}` **S??resi Fazla hata verebilir!**"
            )
        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("?????? Butonlar", callback_data="men??"),
                    InlineKeyboardButton("??? Kapat", callback_data="cls"),
                ],[
                    InlineKeyboardButton("???? Kanal", url=f"https://t.me/Sohbetdestek")
                ],
            ]
        )
        file_name = get_file_name(audio)
        title = file_name
        thumb_name = "https://telegra.ph/file/cd0b87484429704c7b935.png" 
        thumbnail = thumb_name
        duration = round(audio.duration / 60)
        views = "Yerel olarak eklendi"
        requested_by = message.from_user.first_name
        await generate_cover(requested_by, title, views, duration, thumbnail)
        file_path = await convert(
            (await message.reply_to_message.download(file_name))
            if not path.isfile(path.join("downloads", file_name))
            else file_name
        )
    elif urls:
        query = toxt
        await lel.edit("???? **??ark?? devam ediyor...**")
        ydl_opts = {"format": "bestaudio[ext=m4a]"}
        try:
            results = YoutubeSearch(query, max_results=1).to_dict()
            url = f"https://youtube.com{results[0]['url_suffix']}"
            # print(results)
            title = results[0]["title"][:25]
            thumbnail = results[0]["thumbnails"][0]
            thumb_name = f"thumb{title}.jpg"
            thumb = requests.get(thumbnail, allow_redirects=True)
            open(thumb_name, "wb").write(thumb.content)
            duration = results[0]["duration"]
            results[0]["url_suffix"]
            views = results[0]["views"]

        except Exception as e:
            await lel.edit(
                "**??ark?? bulunamad??.** Daha net bir ba??l??k par??as?? aramay?? deneyin, Yaz `/help` Yard??ma ihtiyac??n olursa."
            )
            print(str(e))
            return
        dlurl=url
        dlurl=dlurl.replace("youtube","youtubepp")
        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("?????? Butonlar", callback_data="menu"),
                    InlineKeyboardButton("??? Kapat", callback_data="cls"),
                ],[
                    InlineKeyboardButton("???? Kanal", url=f"https://t.me/Sohbetdestek")
                ],
            ]
        )
        requested_by = message.from_user.first_name
        await generate_cover(requested_by, title, views, duration, thumbnail)
        file_path = await convert(youtube.download(url))        
    else:
        query = ""
        for i in message.command[1:]:
            query += " " + str(i)
        print(query)
        #await lel.edit("???? **????leniyor...**")
        ydl_opts = {"format": "bestaudio[ext=m4a]"}
        
        try:
          results = YoutubeSearch(query, max_results=5).to_dict()
        except:
          await lel.edit("**??alacak ??ark??n??n ad??n?? ver!**")
        # Looks like hell. Aren't it?? FUCK OFF
        try:
            toxxt = "\n"
            j = 0
            useer=user_name

            emojilist = ["1??????","2??????","3??????","4??????","5??????"]
            while j < 5:
                toxxt += f"{emojilist[j]} [{results[j]['title']}](https://youtube.com{results[j]['url_suffix']})</b>\n"
                toxxt += f" ?????? **Duration** - {results[j]['duration']}\n"
                toxxt += f" ?????? G????lendirilmi?? ProMusicAsistan\n\n"

                j += 1            
            koyboard = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton("1??????", callback_data=f'plll 0|{query}|{user_id}'),
                        InlineKeyboardButton("2??????", callback_data=f'plll 1|{query}|{user_id}'),
                    ],
                    [
                        InlineKeyboardButton("3??????", callback_data=f'plll 2|{query}|{user_id}'),
                        InlineKeyboardButton("4??????", callback_data=f'plll 3|{query}|{user_id}'),
                        InlineKeyboardButton("5??????", callback_data=f'plll 4|{query}|{user_id}'), 
          
                    ],
                    [
                        InlineKeyboardButton(text="??? Kapat", callback_data="cls")],
                ]
            )
     
            await message.reply_photo(
                photo="https://i.ibb.co/khRz42f/Turkish-Voice.jpg",
                caption=toxxt, reply_markup=koyboard, 
            )
            await lel.delete()
            return
            # Returning to pornhub
        except:
            #await lel.edit("???? **Aralar??ndan se??im yapabilece??iniz yeterli sonu?? yok, hemen oynamaya ba??lay??n.**")
                        
            # print(results)
            try:
                url = f"https://youtube.com{results[0]['url_suffix']}"
                title = results[0]["title"][:40]
                thumbnail = results[0]["thumbnails"][0]
                thumb_name = f"thumb{title}.jpg"
                thumb = requests.get(thumbnail, allow_redirects=True)
                open(thumb_name, "wb").write(thumb.content)
                duration = results[0]["duration"]
                results[0]["url_suffix"]
                views = results[0]["views"]

            except Exception as e:
                await lel.edit(
                "??? **??ark?? bulunamad??!** l??tfen do??ru ??ark?? ad??n?? girin."
            )
                print(str(e))
                return
            dlurl=url
            dlurl=dlurl.replace("youtube","youtubepp")
            keyboard = InlineKeyboardMarkup(
                    [
                [
                    InlineKeyboardButton("?????? Butonlar", callback_data="men??"),
                    InlineKeyboardButton("??? Kapat", callback_data="cls"),
                ],[
                    InlineKeyboardButton("???? Kanal", url=f"https://t.me/Sohbetdestek")
                ],
            ]
        )
            requested_by = message.from_user.first_name
            await generate_cover(requested_by, title, views, duration, thumbnail)
            file_path = await convert(youtube.download(url))   
    chat_id = get_chat_id(message.chat)
    if chat_id in callsmusic.pytgcalls.active_calls:
        position = await queues.put(chat_id, file=file_path)
        qeue = que.get(chat_id)
        s_name = title
        r_by = message.from_user
        loc = file_path
        appendable = [s_name, r_by, loc]
        qeue.append(appendable)
        await message.reply_photo(
            photo="final.png",
            caption = f"???? **Par??an??n ismi:** [{title[:30]}]({url})\n??? **??ark??n??n s??resi:** {duration}\n?????? **Durum:** S??raya Al??nd?? `{position}`\n" \
                    + f"???? **Talep eden ki??i:** {message.from_user.mention}",
                   reply_markup=keyboard)
       
    else:
        chat_id = get_chat_id(message.chat)
        que[chat_id] = []
        qeue = que.get(chat_id)
        s_name = title
        r_by = message.from_user
        loc = file_path
        appendable = [s_name, r_by, loc]
        qeue.append(appendable)
        try:
            callsmusic.pytgcalls.join_group_call(chat_id, file_path)
        except:
            message.reply("**Sesli Sohbet Grubu kapal??, Kat??lamam.**")
            return
        await message.reply_photo(
            photo="final.png",
            caption = f"???? **Par??an??n ismi:** [{title[:30]}]({url})\n??? **??ark??n??n s??resi:** {duration}\n???? **Durum:** Oynat??l??yor\n" \
                    + f"???? **??stek:** {message.from_user.mention}",
                   reply_markup=keyboard)

    os.remove("final.png")
    return await lel.delete()


@Client.on_callback_query(filters.regex(pattern=r"plll"))
async def lol_cb(b, cb):
    global que
    cbd = cb.data.strip()
    chat_id = cb.message.chat.id
    typed_=cbd.split(None, 1)[1]
    try:
        x,query,useer_id = typed_.split("|")      
    except:
        await cb.message.edit("??? ??ark?? bulunamad??")
        return
    useer_id = int(useer_id)
    if cb.from_user.id != useer_id:
        await cb.answer("Siz bu ??ark??y?? isteyen insanlar de??ilsiniz.!", show_alert=True)
        return
    #await cb.message.edit("???? **Ba??lat??l??yor...**")
    x=int(x)
    try:
        useer_name = cb.message.reply_to_message.from_user.first_name
    except:
        useer_name = cb.message.from_user.first_name
    results = YoutubeSearch(query, max_results=6).to_dict()
    resultss=results[x]["url_suffix"]
    title=results[x]["title"][:25]
    thumbnail=results[x]["thumbnails"][0]
    duration=results[x]["duration"]
    views=results[x]["views"]
    url = f"https://www.youtube.com{resultss}"
    try:    
        secmul, dur, dur_arr = 1, 0, duration.split(":")
        for i in range(len(dur_arr)-1, -1, -1):
            dur += (int(dur_arr[i]) * secmul)
            secmul *= 60
        if (dur / 60) > DURATION_LIMIT:
             await cb.message.edit(f"??? S??resi daha fazla olan ??ark??lar `{DURATION_LIMIT}` dakika ??al??namaz.")
             return
    except:
        pass
    try:
        thumb_name = f"thumb-{title}cybermusic.jpg"
        thumb = requests.get(thumbnail, allow_redirects=True)
        open(thumb_name, "wb").write(thumb.content)
    except Exception as e:
        print(e)
        return
    dlurl=url
    dlurl=dlurl.replace("youtube", "youtubepp")
    keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("?????? Butonlar", callback_data="men??"),
                    InlineKeyboardButton("??? Kapat", callback_data="cls"),
                ],[
                    InlineKeyboardButton("???? Kanal", url=f"https://t.me/Sohbetdestek")
                ],
            ]
    )
    requested_by = useer_name
    await generate_cover(requested_by, title, views, duration, thumbnail)
    file_path = await converter.convert(youtube.download(url))  
    if chat_id in callsmusic.pytgcalls.active_calls:
        position = await queues.put(chat_id, file=file_path)
        qeue = que.get(chat_id)
        s_name = title
        try:
            r_by = cb.message.reply_to_message.from_user
        except:
            r_by = cb.message.from_user
        loc = file_path
        appendable = [s_name, r_by, loc]
        qeue.append(appendable)
        await cb.message.delete()
        await b.send_photo(
        chat_id,
        photo="final.png",
        caption=f"???? **S??raya eklenen par??a**\n\n???? **??smi:** [{title[:35]}]({url})\n??? **??ark??n??n s??resi:** `{duration}`\n???? **Talep eden ki??i:** {r_by.mention}\n" \
               +f"???? **Konumda s??raya al??nd??:** ?? `{position}` ??",
        reply_markup=keyboard,
        )
        os.remove("final.png")
    else:
        que[chat_id] = []
        qeue = que.get(chat_id)
        s_name = title
        try:
            r_by = cb.message.reply_to_message.from_user
        except:
            r_by = cb.message.from_user
        loc = file_path
        appendable = [s_name, r_by, loc]
        qeue.append(appendable)
        callsmusic.pytgcalls.join_group_call(chat_id, file_path)
        await cb.message.delete()
        await b.send_photo(
        chat_id,
        photo="final.png",
        caption=f"???? **??ark??n??n ismi:** [{title[:35]}]({url})\n??? **??ark??n??n s??resi:** `{duration}`\n???? **Durum:** `Oynat??l??yor`\n" \
               +f"???? **Talep eden:** {r_by.mention}",
        reply_markup=keyboard,
        )
        os.remove("final.png")
 
