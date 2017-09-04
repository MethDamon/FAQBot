#!/usr/bin/env python
# -*- coding: utf-8 -*-

import math
import os
import re
import os.path
import requests
import logging

import xlrd as xlrd

from slackclient import SlackClient
from nltk.corpus import stopwords
from collections import Counter
from pprint import pprint

bot_token = os.environ['TOKEN']

sc = SlackClient(bot_token)

channels = []

greetings = ['hi', 'hey', 'hello', 'hallo']

users = []

myself_id = ''


def read_in_faq():
    wb = xlrd.open_workbook("/root/faqbot/faq.xlsx")
    sh = wb.sheet_by_index(0)
    d = {}
    i = 1
    while i < sh.nrows:
        question = sh.cell(i, 0).value
        answer = sh.cell(i, 1).value
        d[question] = answer
        i += 1
    return d

questions_and_answers = read_in_faq()

insults = ['stupid', 'idiot', 'bad', 'fuck', 'fucking', 'moron', 'cunt', 'ass', 'asshole']

answers = [answer for answer in questions_and_answers.values()]
questions = []


def prepare():
    stop_set = set(stopwords.words('english'))
    questions_tokenized = [set(re.findall(r"[\w']+", question.lower())) for question in questions_and_answers.keys()]
    global questions
    questions = [Counter([word for word in question if word not in stop_set]) for question in questions_tokenized]


def question_to_vector(question):
    vector = set(re.findall(r"[\w']+", question.lower()))
    return Counter(vector)


def get_cosine(vec1, vec2):
    intersection = set(vec1.keys()) & set(vec2.keys())
    numerator = sum([vec1[x] * vec2[x] for x in intersection])

    sum1 = sum([vec1[x]**2 for x in vec1.keys()])
    sum2 = sum([vec2[x]**2 for x in vec2.keys()])
    denominator = math.sqrt(sum1) * math.sqrt(sum2)

    if not denominator:
        return 0.0
    else:
        return float(numerator) / denominator


def get_answer(v1):
    highest_sim = 0
    highest_vect = None

    for question in questions:
        sim = get_cosine(v1, question)
        if sim > highest_sim:
            highest_sim = sim
            highest_vect = question

    if highest_sim < 0.1:
        return ""

    index = questions.index(highest_vect)
    return answers[index]

prepare()


def connect():
    if sc.rtm_connect():
        print("Bot is connected")
        users = sc.api_call("users.list")
        for user in users['members']:
            if user['name'] == 'mrjames':
                myself_id = user['id']
        while True:
            messages = sc.rtm_read()
            for message in messages:
                pprint(message)
                if 'type' in message.keys and message['type'] == 'error' and message['error']['code']:
                    connect()
                elif 'type' in message.keys() and message['type'] == 'message':
                    lower_text = message['text'].lower()
                    question_without_mentioning = message['text'].replace('<@' + myself_id + '>', '').replace('<http://modum.io|modum.io>', 'modum.io')
                    text_cleaned = question_without_mentioning.replace(".io", "").replace("\'", "").lower()
                    if lower_text.startswith('<@' + myself_id.lower() + '>'):
                        answer = ""
                        if any(insult in text_cleaned for insult in insults):
                            print("insult detected")
                            answer = '<@' + message['user'] + "> Hey look, I know I'm not *that* bright, but I'm pretty sure that was an insult. Please be kind with me or I'll come for your circuit board!"
                            sc.rtm_send_message(message['channel'], "*Answer* " + answer)
                        else:
                            if any(greeting in question_to_vector(text_cleaned).keys() for greeting in greetings) and not text_cleaned.endswith('?'):
                                print("greeting detected")
                                answer = '<@' + message['user'] + "> Hey! Feel free to ask me a question!"
                                sc.rtm_send_message(message['channel'], "*Answer* " + answer)
                            elif text_cleaned.endswith('?'):
                                print("question detected")
                                sc.rtm_send_message(message['channel'], '<@' + message['user'] + "> I think you asked a question. I will try my best to answer it. Beep! :robot_face:")
                                sc.rtm_send_message(message['channel'], '*Question*: ' + question_without_mentioning)
                                if all(word in text_cleaned for word in 'how are you'.split()):
                                    answer = "I'm good, thanks for asking!"
                            else:
                                vector = question_to_vector(text_cleaned)
                                answer = get_answer(vector)
                                if answer == "":
                                    answer = "Sorry, I'm not *that* clever. Please ask one of the team members"
                                    file = open("/root/faqbot/questions_failed.txt", "a")
                                    file.write(question_without_mentioning + "\n\n")
                                    file.close()
                                    sc.rtm_send_message(message['channel'], "*Answer* " + answer)
                                else:
                                    vector = question_to_vector(text_cleaned)
                                    answer = get_answer(vector)
                                    if answer == "":
                                        answer = "Sorry, I'm not *that* clever. Please ask one of the team members"
                                        file = open("questions_failed.txt", "a")
                                        file.write(question_without_mentioning + "\n\n")
                                        file.close()
                                        sc.rtm_send_message(message['channel'], "*Answer* " + answer)
                                    else:
                                        answer = get_answer(question_to_vector(text_cleaned))
                                        sc.rtm_send_message(message['channel'], "*Answer* " + answer)
                    else:
                        sc.rtm_send_message(message['channel'], "Sorry, but I think that wasn't a question. Make sure to add a question mark at the end!")
    else:
        print('Connection Failed')

connect()
