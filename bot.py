import configparser
import discord
import sqlite3
from datetime import datetime, timedelta
from resp import player_stats, online_AAS
from dbase import insert_data, get_steam_id
from discord.ext import commands, tasks
from discord import app_commands
from rekrut import add_recruit_to_db, get_all_recruits, remove_recruit_from_db, get_recruit_time
from golosovanie import add_vote_session, get_votes, remove_vote_session, get_all_recruits1
import asyncio
import os

# Читаем конфиг с указанием кодировки
config = configparser.ConfigParser()

# Открываем файл с явным указанием кодировки
with open("config.cfg", "r", encoding="utf-8") as f:
    config.read_file(f)

TOKEN = os.getenv("TOKEN")
#TOKEN = config["TOKEN"]["token"]
msg_rekrut_sq = config["MSG"]["msg_sq"]
msg_rekrut_a3 = config["MSG"]["msg_a3"]
stats_status = config["PLUGINS"]["stats_status"]
role_join_now = config["PLUGINS"]["role_join_now"]
DAY_FOR_INV = config["SETTINGS"]["day_for_inv"]
rekrut_time = config["PLUGINS"]["rekrut_time"]



'''
ROLE_HIERARCHY = [
	"Рекрут", 0
	"Стрелок", 1
	"Штурмовик", 2
	"Младший командир",  3
	"Штурмовой командир",4
	"Командир стороны",  5
	"Старший командир",  6
	"Командир отряда на Broken Arrow",7
	"Командир отряда на Squad", 8
	"Командир отряда на Squad", 9
	"Предиктор" 10
]

ROLE_GAMES = [
   "Squad",
   "Arma 3",
   "Broken Arrow"

ROLE_DIFRENTS =[
	"Косячник" 0
]
]'''
ROLE_PLAYERS = [ 
   1227927464916025444,
   1186912800547811389,
   1186912762018926662,
   1233029491908149351,
   1186911102043435100,
   1254831503121059900,
   1186907996073238610,
   1379031511470309496,
   1326482260861390942,
   1326482924828098630,
   1233420465499017319
]
ROLE_GAMES = [
   1271939696880124026,
   1254833937834836142,
   1379032056289562634
]
ROLE_DIFRENTS = [
	1188411429989134366
]

LOG_CHANNEL_ID = 1318896486821658624  # 👈 ВОТ СЮДА вставь ID канала logs
DECITED_CHANNEL_ID  = 1320713497075781703 # канал кадров в который будут отправляться повышения
stats_chan_id = 1330947492237414480 #id канала где будет работать !рекрут и !statsreg и !stats
golos_chan_sq_id = 1348249312257118260 #id голосового канала сквад



intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)






@tasks.loop(minutes=120)  # Проверка каждый 56 минут
async def check_recruits():
	"""Проверка всех голосований и рекрутов, которые не завершены"""
	now = datetime.now()
	print(f"[BOT] Запуск проверки на {now}")

	# Преобразуем day_for_inv в число, если это строка
	try:
		day_for_inv_int = int(DAY_FOR_INV)
	except ValueError:
		print(f"[BOT] Ошибка: DAY_FOR_INV должно быть числом, но получено {DAY_FOR_INV}")
		return

	# Проверка старых голосований в базе данных
	conn = sqlite3.connect('votes.db')
	c = conn.cursor()
	c.execute("SELECT message_id, discord_id, created_at FROM vote_sessions WHERE result IS NULL")
	votes = c.fetchall()
	conn.close()

	print(f"[BOT] Найдены голосования: {len(votes)}")

	# Проверяем каждое голосование
	for vote in votes:
		message_id, discord_id, created_at = vote
		created_at = datetime.strptime(created_at, '%Y-%m-%d %H:%M:%S')

		# Если прошло больше 24 часов, то обрабатываем голосование
		if now - created_at >= timedelta(days=2):  # Параметр 1 день
			channel = bot.get_channel(golos_chan_sq_id)  # Получаем канал для голосования
			await schedule_vote_result(message_id, channel, discord_id)
		else:
			print(f"[BOT] Голосование с message_id {message_id} ещё не вышло по времени")

	# Проверка рекрутов, которые прошли необходимое время
	recruits = get_all_recruits()
	print(f"[BOT] Найдено рекрутов: {len(recruits)}")
	for recruit in recruits:
		discord_id, time_added = recruit
		time_added = datetime.strptime(time_added, '%Y-%m-%d %H:%M:%S')
		if now - time_added >= timedelta(days=day_for_inv_int):  # Используем целое число
			# Удаляем рекрута из базы
			remove_recruit_from_db(discord_id)

			# Получаем пользователя по ID
			user = await bot.fetch_user(discord_id)

			# Создаем голосование
			print(f"[BOT] Создал голосование по {user.name}")
			channel = bot.get_channel(golos_chan_sq_id)
			message = await channel.send(
				f"<@&{ROLE_GAMES[0]}>\n"
				f"Прошло {day_for_inv_int} дней с тех пор, как {user.mention} получил роль 'Кандидат'. Нужно решить, оставить ли его.\n"
				"Проголосуйте: ✅ для принятия, ❌ для исключения."
			)
			await message.add_reaction("✅")
			await message.add_reaction("❌")

			# Сохраняем информацию о голосовании в базу данных
			add_vote_session(message.id, discord_id)

			# Запланировать подсчёт голосов через 24 часа
			await schedule_vote_result(message.id, channel, discord_id)

async def count_votes_from_reactions(message):
	"""Подсчитывает количество голосов за и против из реакций на сообщение"""
	vote_yes = 0
	vote_no = 0

	# Получаем все реакции на сообщение
	for reaction in message.reactions:
		# Если реакция - это "✅" (за), увеличиваем счетчик голосов за
		if reaction.emoji == "✅":
			vote_yes = reaction.count - 1  # -1 потому что учитывается реакция бота
		# Если реакция - это "❌" (против), увеличиваем счетчик голосов против
		elif reaction.emoji == "❌":
			vote_no = reaction.count - 1  # -1 потому что учитывается реакция бота

	return vote_yes, vote_no


async def schedule_vote_result(message_id, channel, discord_id):
	"""Подсчитывает голоса и принимает решение"""
	await asyncio.sleep(15)  # Заменить на 86400 секунд для 24 часов в реальной ситуации

	# Логирование перед получением сообщения
	print(f"[BOT] Получаем сообщение с message_id: {message_id} в канале {channel.id}")

	try:
		# Получаем сообщение по ID
		message = await channel.fetch_message(message_id)
	except discord.errors.NotFound:
		print(f"[BOT] Ошибка: Сообщение с message_id {message_id} не найдено.")
		return  # Прерываем выполнение, если сообщение не найдено

	# Получаем голоса из базы данных

	vote_yes, vote_no = await count_votes_from_reactions(message)
	print(f"[BOT] Голоса для сообщения {message_id}: ✅ {vote_yes}, ❌ {vote_no}")

	# Получаем рекрута (пользователя)
	recruit = await bot.fetch_user(discord_id)

	# Получаем члена сервера с помощью fetch_member
	try:
		member = await channel.guild.fetch_member(discord_id)
	except discord.errors.NotFound:
		print(f"[BOT] Ошибка: Пользователь с ID {discord_id} не найден на сервере.")
		return  # Прерываем выполнение, если пользователь не найден на сервере

		
	# Применяем логику в зависимости от результата
	if vote_yes > vote_no:
		# Даем роль рекруту
		role_new = discord.utils.get(channel.guild.roles, id =ROLE_PLAYERS[1])  # Название роли
		role_old = discord.utils.get(channel.guild.roles, id =ROLE_PLAYERS[0])
		if role_new:
			await member.remove_roles(role_old)
			await member.add_roles(role_new)
			await channel.send(f"Голосование окончено.{recruit.mention} принят в клан!(за - {vote_yes}, против - {vote_no})")
			await recruit.send(f"Вы были приняты в клан DSHB. Добро пожаловать {recruit.name}!")
		else:
			print(f"[BOT] Ошибка: Роль 'Рекрут' не найдена на сервере.")
	elif vote_no > vote_yes:
		# Убираем все роли рекруту и отправляем личное сообщение
		await recruit.send("Вы не были приняты в клан DSHB, мне жаль.(")
		await channel.send(f"Голосование окончено.{recruit.mention} не был принят в клан(за - {vote_yes}, против - {vote_no}).")
		#Удаляем все роли
		for role in member.roles:
		   if role.name != "@everyone":
			   await member.remove_roles(role)
	else:
		# 50 на 50
		await channel.send(f"<@&{ROLE_GAMES[0]} Голосование за {recruit.mention} завершилось ничьей (50 на 50), ПРИМИТЕ РЕШЕНИЕ.")

	# Удаляем голосование из базы данных после завершения
	remove_vote_session(message_id)


#UPDATE STATUS SERVERS
async def update_status():
    while True:
        server_info = online_AAS()
        if server_info != 404:
	        await bot.change_presence(activity=discord.Game(name=server_info))
	        await asyncio.sleep(20) 








# Событие готовности
@bot.event
async def on_ready():

	await bot.tree.sync()
	print(f"[BOT] Бот запущен как {bot.user}")

	#if rekrut_time == True:
	check_recruits.start()  # Запуск проверки раз в час
	bot.loop.create_task(update_status())







@bot.event
async def on_member_join(member):
	if role_join_now == False:
		return
	# Замените 'Рекрут' на название вашей роли
	role_name = "Гость"  
	
	# Ищем роль по имени
	role = discord.utils.get(member.guild.roles, name=role_name)
	
	# Если роль существует, даём её новому участнику
	if role:
		log_chan = member.guild.get_channel(LOG_CHANNEL_ID) 
		await member.add_roles(role)
		await log_chan.send(f"{member.mention} получил {role_name}")




# КОМАНДА ЧТОБЫ ПОНИЗИТЬ
@bot.tree.context_menu(name="Понизить")
async def greet_user(interaction: discord.Interaction, user: discord.User):
	# Говорим Discord, что ответ будет позже
	await interaction.response.defer(ephemeral=True)

	member = interaction.guild.get_member(user.id)
	user_member = interaction.guild.get_member(interaction.user.id)  # Это тот, кто нажал на кнопку

	if member is None:
		return  # молча, без ответа

	# Получаем ID последней роли
	last_role_id_member = member.roles[-1].id
	last_role_id_user = user_member.roles[-1].id

	if last_role_id_user in ROLE_PLAYERS:
		if last_role_id_member in ROLE_PLAYERS:
			role_index_member = ROLE_PLAYERS.index(last_role_id_member)
			role_index_user = ROLE_PLAYERS.index(last_role_id_user)

			# Проверяем, если роль инициатора меньше Штурмового командира, он ничего не делает
			if role_index_user < 4:
				await interaction.followup.send("Ты ещё не коммандир!", ephemeral=True)
				return

			# Блокируем попытку понижения самого себя
			if interaction.user.name == user.name:
				await interaction.followup.send("Ты не можешь понижать самого себя!", ephemeral=True)
				return

			# Проверка на попытку понижения людей выше себя и своего уровня
			if role_index_user < role_index_member or role_index_user == role_index_member:
				await interaction.followup.send("Ты не можешь понижать человека выше себя и своего уровня!", ephemeral=True)
				return

			else:
				# Получаем объект роли для понижения
				new_role = interaction.guild.get_role(ROLE_PLAYERS[role_index_member -1])
				old_role = interaction.guild.get_role(ROLE_PLAYERS[role_index_member])


				# Добавляем новую роль и удаляем старую
				await member.add_roles(new_role)
				await member.remove_roles(old_role)
				await ctx.author.send(f"Ты понижен до {new_role.name}")
				await interaction.followup.send(f"Ты понизил {user.mention} до {new_role.name}", ephemeral=True)
				print(f"[BOT] {interaction.user.name}({interaction.user.mention}) remove role - {user.name}({user.mention})")

				log_chan = interaction.guild.get_channel(LOG_CHANNEL_ID)
				dec_chan = interaction.guild.get_channel(DECITED_CHANNEL_ID)

				if log_chan:
					await log_chan.send(f"{interaction.user.mention} понизил {user.mention} до {new_role.name}")
				else:
					print("[ERROR] Канал логов не найден")

				if dec_chan:
					await dec_chan.send(f"{user.mention} понижен до {new_role.name}!")
				else:
					print("[ERROR] Канал кадров не найден")
		else:
			print("[ERROR] Роль не найдена в списке!")
	else:
		await interaction.followup.send(f"Ты не можешь понижать {user.mention}  т.к. у нету роли dshb", ephemeral=True)
		print("[ERROR] Роль не найдена в списке!")


# КОМАНДА ЧТОБЫ ПОВЫСИТЬ
@bot.tree.context_menu(name="Повысить")
async def greet_user(interaction: discord.Interaction, user: discord.User):
	# Говорим Discord, что ответ будет позже
	await interaction.response.defer(ephemeral=True)

	member = interaction.guild.get_member(user.id)
	user_member = interaction.guild.get_member(interaction.user.id)  # Это тот, кто нажал на кнопку

	if member is None:
		return  # молча, без ответа

	# Получаем ID последней роли
	last_role_id_member = member.roles[-1].id
	last_role_id_user = user_member.roles[-1].id

	if last_role_id_user in ROLE_PLAYERS:
		if last_role_id_member in ROLE_PLAYERS:
			role_index_member = ROLE_PLAYERS.index(last_role_id_member)
			role_index_user = ROLE_PLAYERS.index(last_role_id_user)

			# Проверяем, если роль инициатора меньше Штурмового, он ничего не делает
			if role_index_user < 4:
				await interaction.followup.send("Ты ещё не коммандир!", ephemeral=True)
				return

			# Блокируем попытку повышения самого себя
			if interaction.user.name == user.name:
				await interaction.followup.send("Ты не можешь повышать самого себя!", ephemeral=True)
				return

			# Проверка на попытку повысить человека на свою роль
			if (role_index_user - 1) == role_index_member:
				await interaction.followup.send("Ты не можешь повышать человека на свою роль", ephemeral=True)
				return

			# Проверка на попытку повышения людей выше себя и своего уровня
			if role_index_user < role_index_member or role_index_user == role_index_member:
				await interaction.followup.send("Ты не можешь повышать человека выше себя и своего уровня!", ephemeral=True)
				return

			else:
				# Получаем объект роли для повышения
				new_role = interaction.guild.get_role(ROLE_PLAYERS[role_index_member + 1])
				old_role = interaction.guild.get_role(ROLE_PLAYERS[role_index_member])

				if role_index_member == 0:
					#Удаляем все роли
					for role in member.roles:
					   if role.name != "@everyone":
						   await member.remove_roles(role)

				# Удаляем старую роль, если это необходимо
				if role_index_member == 0 or role_index_member == 1 or role_index_member == 3:
					await member.remove_roles(old_role)

				# Добавляем новую роль
				await member.add_roles(new_role)
				await ctx.author.send(f"Ты повышен до {new_role.name}")
				await interaction.followup.send(f"Ты повысил {user.mention} до {new_role.name}", ephemeral=True)
				print(f"[BOT] {interaction.user.name}({interaction.user.mention}) add role - {user.name}({user.mention})")

				log_chan = interaction.guild.get_channel(LOG_CHANNEL_ID)
				dec_chan = interaction.guild.get_channel(DECITED_CHANNEL_ID)

				if log_chan:
					await log_chan.send(f"{interaction.user.mention} повысил {user.mention} до {new_role.name}")
				else:
					print("[ERROR] Канал логов не найден")

				if dec_chan:
					await dec_chan.send(f"{user.mention} повышен до {new_role.name}!")
				else:
					print("[ERROR] Канал кадров не найден")
		else:
			print("[ERROR] Роль не найдена в списке!")
	else:
		await interaction.followup.send(f"Ты не можешь повышать {user.mention}  т.к. у нету роли dshb", ephemeral=True)
		print("[ERROR] Роль не найдена в списке!")


# КОМАНДА ЧТОБЫ ВЫДАТЬ РЕКРУТА SQUAD
@bot.tree.context_menu(name="Выдать кандидата SQ")
async def greet_user(interaction: discord.Interaction, user: discord.User):
	# Говорим Discord, что ответ будет позже
	await interaction.response.defer(ephemeral=True)

	member = interaction.guild.get_member(user.id)
	user_member = interaction.guild.get_member(interaction.user.id)  # Это тот, кто нажал на кнопку

	if member is None:
		return  # молча, без ответа

	# Получаем ID последней роли
	last_role_id_member = member.roles[-1].id
	last_role_id_user = user_member.roles[-1].id


	if last_role_id_user in ROLE_PLAYERS:
		#role_index_member = ROLE_PLAYERS.index(last_role_id_member)
		role_index_user = ROLE_PLAYERS.index(last_role_id_user)

		# Проверяем, если роль инициатора меньше Штурмового, он ничего не делает
		if role_index_user < 4:
			await interaction.followup.send("Ты ещё не коммандир!", ephemeral=True)
			return

		# Блокируем попытку повышения самого себя
		if interaction.user.name == user.name:
			await interaction.followup.send("Ты не можешь выдавать себе рекрута!", ephemeral=True)
			return

		# Проверка на попытку повышения людей выше себя и своего уровня
		if role_index_user < role_index_member or role_index_user == role_index_member:
			await interaction.followup.send("Ты не можешь дать роль рекрута человеку выше себя и своего уровня!", ephemeral=True)
			return

		else:
			#Удаляем все роли
			for role in member.roles:
			   if role.name != "@everyone":
				   await member.remove_roles(role)

			#Выдаём новые роли
			new_role = interaction.guild.get_role(ROLE_PLAYERS[0])
			await member.add_roles(new_role)
			new_role_game = interaction.guild.get_role(ROLE_GAMES[0])
			await member.add_roles(new_role_game)

			await interaction.user.send(msg_rekrut_sq)

			#Добавляем в базу id время получения рекрута
			discord_id = user.id
			add_recruit_to_db(discord_id)

			print(f"[BOT] {interaction.user.name}({interaction.user.mention}) add - {user.name}({user.mention}) role({new_role.name})({new_role_game.name})")
			await interaction.followup.send(f"Ты выдал Рекрута {user.mention} по игре  {new_role_game.name}", ephemeral=True)

			log_chan = interaction.guild.get_channel(LOG_CHANNEL_ID)
			dec_chan = interaction.guild.get_channel(DECITED_CHANNEL_ID)

			if log_chan:
				await log_chan.send(f"{interaction.user.mention} выдал {user.mention} роль {new_role.name} по игре {new_role_game.name}")
			else:
				print("[ERROR] Канал логов не найден")

			if dec_chan:
				await dec_chan.send(f"{user.mention} теперь Рекрут клана в игре {new_role_game.name}!")
			else:
				print("[ERROR] Канал кадров не найден")
	else:
		await interaction.followup.send(f"Ты не командир DSHB!", ephemeral=True)


# КОМАНДА ЧТОБЫ ВЫДАТЬ РЕКРУТА ARMA3
@bot.tree.context_menu(name="Выдать кандидата A3")
async def greet_user(interaction: discord.Interaction, user: discord.User):
	# Говорим Discord, что ответ будет позже
	await interaction.response.defer(ephemeral=True)

	member = interaction.guild.get_member(user.id)
	user_member = interaction.guild.get_member(interaction.user.id)  # Это тот, кто нажал на кнопку

	if member is None:
		return  # молча, без ответа

	# Получаем ID последней роли
	last_role_id_member = member.roles[-1].id
	last_role_id_user = user_member.roles[-1].id

	if last_role_id_user in ROLE_PLAYERS:
		#role_index_member = ROLE_PLAYERS.index(last_role_id_member)
		role_index_user = ROLE_PLAYERS.index(last_role_id_user)
		# Проверяем, если роль инициатора меньше Штурмового, он ничего не делает
		if role_index_user < 4:
			await interaction.followup.send("Ты ещё не коммандир!", ephemeral=True)
			return

		# Блокируем попытку повышения самого себя
		if interaction.user.name == user.name:
			await interaction.followup.send("Ты не можешь выдавать себе рекрута!", ephemeral=True)
			return

		#Проверка на попытку повышения людей выше себя и своего уровня
		if role_index_user < role_index_member or role_index_user == role_index_member:
			await interaction.followup.send("Ты не можешь дать роль рекрута человеку выше себя и своего уровня!", ephemeral=True)
			return

		else:
			#Удаляем все роли
			for role in member.roles:
			   if role.name != "@everyone":
				   await member.remove_roles(role)

			#Выдаём новые роли
			new_role = interaction.guild.get_role(ROLE_PLAYERS[0])
			await member.add_roles(new_role)
			new_role_game = interaction.guild.get_role(ROLE_GAMES[1])
			await member.add_roles(new_role_game)
			await ctx.author.send(msg_rekrut_a3)


			print(f"[BOT] {interaction.user.name}({interaction.user.mention}) add - {user.name}({user.mention}) role({new_role.name})({new_role_game.name})")
			await interaction.followup.send(f"Ты выдал Рекрута {user.mention} по игре  {new_role_game.name}", ephemeral=True)

			log_chan = interaction.guild.get_channel(LOG_CHANNEL_ID)
			dec_chan = interaction.guild.get_channel(DECITED_CHANNEL_ID)

			if log_chan:
				await log_chan.send(f"{interaction.user.mention} выдал {user.mention} роль {new_role.name} по игре {new_role_game.name}")
			else:
				print("[ERROR] Канал логов не найден")

			if dec_chan:
				await dec_chan.send(f"{user.mention} теперь Рекрут клана в игре {new_role_game.name}!")
			else:
				print("[ERROR] Канал кадров не найден")
			return
	else:
		await interaction.followup.send(f"Ты не командир DSHB!", ephemeral=True)



'''
# КОМАНДА ЧТОБЫ ВЫДАТЬ КОСЯЧНИКА НА 1 ДЕНЬ ROLE_DIFRENTS[0]
@bot.tree.context_menu(name="Выдать Косячника на 1 день.")
async def greet_user(interaction: discord.Interaction, user: discord.User):
	# Говорим Discord, что ответ будет позже
	await interaction.response.defer(ephemeral=True)

	member = interaction.guild.get_member(user.id)
	user_member = interaction.guild.get_member(interaction.user.id)  # Это тот, кто нажал на кнопку

	if member is None:
		return  # молча, без ответа

	# Получаем ID последней роли
	last_role_id_member = member.roles[-1].id
	last_role_id_user = user_member.roles[-1].id

	if last_role_id_user in ROLE_PLAYERS:
		if last_role_id_member in ROLE_PLAYERS:
			role_index_member = ROLE_PLAYERS.index(last_role_id_member)
			role_index_user = ROLE_PLAYERS.index(last_role_id_user)

			# Проверяем, если роль инициатора меньше Штурмового командира, он ничего не делает
			if role_index_user < 4:
				await interaction.followup.send("Ты ещё не коммандир!", ephemeral=True)
				return

			# Блокируем попытку понижения самого себя
			if interaction.user.name == user.name:
				await interaction.followup.send("Ты не можешь выдать самому себе самого себя!", ephemeral=True)
				return

			# Проверка на попытку понижения людей выше себя и своего уровня
			if role_index_user < role_index_member or role_index_user == role_index_member:
				await interaction.followup.send("Ты не можешь выдавать роль  человеку выше себя и своего уровня!", ephemeral=True)
				return

			else:
				# Получаем объект роли для понижения
				new_role = interaction.guild.get_role(ROLE_DIFRENTS[0])


				# Добавляем новую роль и удаляем старую
				await member.add_roles(new_role)
				await interaction.followup.send(f"Ты выдал {user.mention} роль {new_role.name} на 1 день", ephemeral=True)
				print(f"[BOT] {interaction.user.name}({interaction.user.mention}) remove role - {user.name}({user.mention})")

				log_chan = interaction.guild.get_channel(LOG_CHANNEL_ID)
				dec_chan = interaction.guild.get_channel(DECITED_CHANNEL_ID)

				if log_chan:
					await log_chan.send(f"{interaction.user.mention} выдал {user.mention} роль {new_role.name} на 1 день.")
				else:
					print("[ERROR] Канал логов не найден")

				if dec_chan:
					await dec_chan.send(f"{user.mention} получил {new_role.name} на 1 день.")
				else:
					print("[ERROR] Канал кадров не найден")
		else:
			print("[ERROR] Роль не найдена в списке!")
	else:
		await interaction.followup.send(f"Ты не можешь выдавать {user.mention}  т.к. у нету роли dshb", ephemeral=True)
		print("[ERROR] Роль не найдена в списке!")


# КОМАНДА ЧТОБЫ ВЫДАТЬ КОСЯЧНИКА НА 7 ДЕНЬ ROLE_DIFRENTS[0]
@bot.tree.context_menu(name="Выдать Косячника на 1 день.")
async def greet_user(interaction: discord.Interaction, user: discord.User):
	# Говорим Discord, что ответ будет позже
	await interaction.response.defer(ephemeral=True)

	member = interaction.guild.get_member(user.id)
	user_member = interaction.guild.get_member(interaction.user.id)  # Это тот, кто нажал на кнопку

	if member is None:
		return  # молча, без ответа

	# Получаем ID последней роли
	last_role_id_member = member.roles[-1].id
	last_role_id_user = user_member.roles[-1].id

	if last_role_id_user in ROLE_PLAYERS:
		if last_role_id_member in ROLE_PLAYERS:
			role_index_member = ROLE_PLAYERS.index(last_role_id_member)
			role_index_user = ROLE_PLAYERS.index(last_role_id_user)

			# Проверяем, если роль инициатора меньше Штурмового командира, он ничего не делает
			if role_index_user < 4:
				await interaction.followup.send("Ты ещё не коммандир!", ephemeral=True)
				return

			# Блокируем попытку понижения самого себя
			if interaction.user.name == user.name:
				await interaction.followup.send("Ты не можешь выдать самому себе самого себя!", ephemeral=True)
				return

			# Проверка на попытку понижения людей выше себя и своего уровня
			if role_index_user < role_index_member or role_index_user == role_index_member:
				await interaction.followup.send("Ты не можешь выдавать роль  человеку выше себя и своего уровня!", ephemeral=True)
				return

			else:
				# Получаем объект роли для понижения
				new_role = interaction.guild.get_role(ROLE_DIFRENTS[0])


				# Добавляем новую роль и удаляем старую
				await member.add_roles(new_role)
				await interaction.followup.send(f"Ты выдал {user.mention} роль {new_role.name} на 7 дней", ephemeral=True)
				print(f"[BOT] {interaction.user.name}({interaction.user.mention}) remove role - {user.name}({user.mention})")

				log_chan = interaction.guild.get_channel(LOG_CHANNEL_ID)
				dec_chan = interaction.guild.get_channel(DECITED_CHANNEL_ID)

				if log_chan:
					await log_chan.send(f"{interaction.user.mention} выдал {user.mention} роль {new_role.name} на 7 дней.")
				else:
					print("[ERROR] Канал логов не найден")

				if dec_chan:
					await dec_chan.send(f"{user.mention} получил {new_role.name} на 7 дней.")
				else:
					print("[ERROR] Канал кадров не найден")
		else:
			print("[ERROR] Роль не найдена в списке!")
	else:
		await interaction.followup.send(f"Ты не можешь выдавать {user.mention}  т.к. у нету роли dshb", ephemeral=True)
		print("[ERROR] Роль не найдена в списке!")

'''

#РЕГИСТРИРУЕТ STEAMID В БАЗЕ
@bot.command()
async def statsreg(ctx, steamid: str = None):
	
	if not steamid.isdigit():  # Проверка, состоит ли строка только из цифр
		await ctx.send(f"Ошибка: '{steamid}' не является числовым Steam ID.")
		return


	steamid = int(steamid)
	if stats_status == False:
		return

	if ctx.channel.id != stats_chan_id:
		return

	if not steamid:
		# Если данных нет, отправляем сообщение
		await ctx.send("Пожалуйста, введите steamid.", ephemeral=True)
		return

	user_id = ctx.author.id
	if insert_data(user_id,steamid) == 0:
		await ctx.send("Не верная длина steamid", ephemeral=True)
		return
	else:
		await ctx.send(f"Твой steamid({steamid}) зарегистрирован!", ephemeral=True)
		return





#ОТПРАВЛЯЕТ СТАТУТ С SQSTATS
@bot.command()
async def stats(ctx):

	if stats_status == False:
		return
	if ctx.channel.id != stats_chan_id:
		return

	user_id = ctx.author.id

	if get_steam_id(user_id) == 343:
		await interaction.followup.send("Ты не зарегистрировал steamid, используй !statsreg <steamid>", ephemeral=True)
		return

	try:
		player_stat = player_stats(get_steam_id(user_id))

		# Создаем Embed для красивого оформления
		embed = discord.Embed(
			title=f"Стата {player_stat['nick']} ",
			description=f"**К/Д:** {player_stat['kd']}\n"
						f"**Винрейт:** {player_stat['winrate']}\n"
						f"**Онлайн:** {player_stat['ОНЛАЙН']}\n"
						f"**Убийства:** {player_stat['УБИЙСТВА']} | **Смерти:** {player_stat['СМЕРТИ']}\n"
						f"**Кит:** {next(iter(player_stat))} | **Время:** {player_stat[next(iter(player_stat))]}\n"
						f"**Поднятия:** {player_stat['ПОДНЯТИЯ']} | **Тимкиллы:** {player_stat['ТИМКИЛЛЫ']}\n"
						f"**Матчи:** {player_stat['МАТЧЕЙ']} | **Урон:** {player_stat['УРОН']}\n"
					  ,
			color=discord.Color.blue()  # Синий цвет для боковой полоски
		)
		# Отправляем embed-сообщение
		await ctx.send(embed=embed,reference=ctx.message)
	except: 
		print(f"Steammid - {steamid}")
		embed = discord.Embed(
				title=f"Стата None",
				description="**Не получилось загрузить.**\n Либо не верный steamid, либо не отвечает сервер.",
				color=discord.Color.blue())
		await ctx.send(embed=embed,reference=ctx.message)



#КОМАНДВ !рекрут
@bot.command(name='рекрут')
async def check_recruit(ctx):
    discord_id = ctx.author.id  # Получаем ID пользователя
    recruit_time = get_recruit_time(discord_id)

    if recruit_time:
        # Преобразуем строку времени в объект datetime
        time_added = datetime.strptime(recruit_time[0], '%Y-%m-%d %H:%M:%S')
        
        # Разница в днях и времени
        time_difference = datetime.now() - time_added
        remaining_days = max(0, (timedelta(days=int(DAY_FOR_INV)) - time_difference).days)
        
        if remaining_days > 0:
            await ctx.send(f"У вас осталось {remaining_days} дня(ей) до конца срока кандидата.")
        else:
            await ctx.send("Ваш срок кандидата истек. Пожалуйста, подождите решения командиров.")
    else:
        await ctx.send("Нет в базе информации!")







@bot.command()
async def hello(ctx):
	await ctx.send("Привет!")

bot.run(TOKEN)