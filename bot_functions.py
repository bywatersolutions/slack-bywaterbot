import csv
import random
import urllib.request


def get_name_to_id_mapping(app):
    name_to_id = {}
    resp = app.client.users_list()
    users = resp["members"]
    for u in users:
        name_to_id[u["profile"]["display_name"].lower()] = u["id"]
        if "name" in u and not u["name"].lower() in name_to_id:
            name_to_id[u["name"].lower()] = u["id"]
        if "real_name" in u and not u["real_name"].lower() in name_to_id:
            name_to_id[u["real_name"].lower()] = u["id"]
    return name_to_id


def get_karma_pep_talks(url):
    urllib.request.urlretrieve(url, "karma.csv")

    karma1, karma2, karma3, karma4 = [], [], [], []

    with open("karma.csv") as csvfile:
        reader = csv.reader(csvfile, delimiter=",", quotechar='"')

        for row in reader:
            if len(row[0]):
                karma1.append(row[0])
            if len(row[1]):
                karma2.append(row[1])
            if len(row[2]):
                karma3.append(row[2])
            if len(row[3]):
                karma4.append(row[3])

    return karma1, karma2, karma3, karma4


def get_quote(url):
    urllib.request.urlretrieve(url, "quotes.csv")

    quotes = []

    with open("quotes.csv") as csvfile:
        reader = csv.reader(csvfile, delimiter=",", quotechar='"')
        for row in reader:
            if len(row[0]):
                quotes.append(row[0])

    quote = random.choice(quotes)

    if quote.startswith("PQ: "):
        quote = quote.replace("PQ: ", "Partner Quote: ", 1)
    elif quote.startswith("HAHA: "):
        quote = quote.replace("HAHA: ", "", 1)
    elif quote.startswith("MOVE: "):
        quote = quote.replace("MOVE: ", "Get up and move! ", 1)
    elif quote.startswith("FACT: "):
        quote = quote.replace("FACT: ", "Fun Fact! ", 1)
    elif quote.startswith("Koha sys pref: "):
        quote = quote.replace(
            "Koha sys pref: ",
            "Koha SysPref Quiz! Do you know what this setting does?",
            1,
        )

    return quote


def get_putdowns():
    putdowns = [
        "you’re a gray sprinkle on a rainbow cupcake.",
        "you are more disappointing than an unsalted pretzel.",
        "I’ll never forget the first time we met. But I’ll keep trying.",
        "It’s impossible to underestimate you.",
        "I thought of you today. It reminded me to take out the trash.",
        "you are like a cloud. When you disappear, it’s a beautiful day.",
        "you have miles to go before you reach mediocre.",
        "I was today years old when I realized I didn’t like you.",
        "the jerk store called. They’re running out of you.",
        "life is full of disappointments, and I just added you to the list.",
        "I treasure the time I don’t spend with you.",
    ]
    return putdowns
