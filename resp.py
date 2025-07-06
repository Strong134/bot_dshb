import requests
from bs4 import BeautifulSoup


def convert_to_dict(table):
    x = 1
    i_key = ''
    dict_ = {}
    for i in table:
        if x == 2:
            if '\n' in i:
               key, value = i.split('\n', 1)
               dict_[key] = value
               continue
            x = 1
            dict_[i_key] = i
            continue
        elif x == 1:
            if '\n' in i:
               key, value = i.split('\n', 1)
               dict_[key] = value
               continue
            x = 2
            i_key = i
            continue
    return dict_


def get_first_two_tables(steamid):
    # Составляем URL с нужным SteamID
    url = f"https://sqstat.ru/player/{steamid}"

    # Отправляем GET-запрос на сайт
    response = requests.get(url)
    
    # Проверяем успешность запроса
    if response.status_code == 200:
        # Парсим HTML-контент
        soup = BeautifulSoup(response.text, 'html.parser')

        # Ищем все таблицы
        tables = soup.find_all('table', class_='table')


        stats_dict = {}

        header = soup.find("h1")
        if header != None:
            player_name = header.text.strip()
        else:
            player_name ='Not'

        # Обрабатываем только первые 2 таблицы
        for idx, table in enumerate(tables[:2], start=1):

            # Печатаем строки таблицы
            rows = table.find_all('tr')

            table_dict = {}  # Словарь для текущей таблицы
            for row in rows:
                cols = row.find_all('td')
                if cols:
                    # Печатаем каждую строку и её ячейки для диагностики
                    row_data = [col.text.strip() for col in cols]
                    #print(row_data)
  
                    stats_dict.update(convert_to_dict(row_data))
        stats_dict['nick'] = player_name
        return stats_dict
    else:
        return f"Ошибка при загрузке страницы: {response.status_code}"


def convert_to_float(value):
    if value:
        if ',' in value:
            value = value.replace(',', '')  # Убираем запятую
            try:
                return float(value)  # Преобразуем строку в число
            except ValueError:
                return None  # Возвращаем None, если преобразовать не удалось
    return None

def convert_to_int(value):
    if value:
        value = value.replace(',', '')  # Убираем запятую
        try:
            return int(value)  # Преобразуем в целое число
        except ValueError:
            return None  # Если преобразование не удалось
    return None



def player_stats(steamid):

    player_stats = get_first_two_tables(steamid)

    #ПОДСЧЁТ КД
    kd  = float(convert_to_float(player_stats.get("УБИЙСТВА")))/ float(convert_to_float(player_stats.get("СМЕРТИ")))
    player_stats['kd'] = str(round(kd,2))

    #ПОДСЧЁТ ВИНРЕЙТА
    winrate  = int(convert_to_int(player_stats.get("ПОБЕД")))/ int(convert_to_int(player_stats.get("МАТЧЕЙ"))) * 100
    player_stats['winrate'] = f"{round(winrate,1)}%"

    return player_stats

#Онлайн и карта сервера AAS
def online_AAS():
    # URL страницы
    url = 'https://www.battlemetrics.com/servers/squad/18129039'

    # Отправляем запрос
    response = requests.get(url)

    # Проверяем успешность запроса
    if response.status_code == 200:

        # Парсим HTML-контент
        soup = BeautifulSoup(response.text, 'html.parser')

        # Ищем информацию о карте
        map_name = soup.find('dt', string='Map').find_next('dd').text.strip()

        # Ищем информацию о количестве игроков
        player_count = soup.find('dt', string='Player count').find_next('dd').text.strip()

        # Выводим в нужном формате
        result = f'[RU][AAS]({player_count})  {map_name}'
        return result
    else:
        return 404