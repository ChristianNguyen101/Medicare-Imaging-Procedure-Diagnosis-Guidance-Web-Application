#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Jan 24 11:19:44 2025

@author: christian_nguyen
"""

from flask import Flask, render_template, request, redirect, url_for
from rich import print
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from difflib import get_close_matches
from app import app

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        procedure = request.form['procedure']
        diagnosis = request.form['diagnosis']
        return redirect(url_for('process', procedure=procedure, diagnosis=diagnosis))
    return render_template('index.html')

@app.route('/process')
def process():
    procedure = request.args.get('procedure')
    diagnosis = request.args.get('diagnosis')

    if not procedure or not diagnosis:
        return "Both Procedure and Diagnosis fields are required.", 400

    P_query = f"cms billing guidelines for {procedure}"
    D_query = f"{diagnosis} ICD-10 code"
    P_url = f"https://www.google.com/search?q={P_query}"
    D_url = f"https://www.google.com/search?q={D_query}"

    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    driver = webdriver.Chrome(options=options)

    try:
        driver.get(D_url)
        wait = WebDriverWait(driver, 10)

        xpaths = [
            '//mark',
            '//span[contains(text(), "ICD-10")]',
            '//div[contains(@class, "BNeawe") and contains(text(), "ICD-10")]',
        ]

        icd_code = None
        for xpath in xpaths:
            try:
                icd_code_element = wait.until(EC.presence_of_element_located((By.XPATH, xpath)))
                icd_code = icd_code_element.text
                break
            except Exception:
                continue

        if not icd_code:
            return "Failed to find ICD-10 code with provided XPaths!", 404

        icd_code = request.args.get('icd_code', icd_code)

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        response = requests.get(P_url, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')

        def extract_results(soup):
            main = soup.select_one("#main")
            if not main:
                return []

            res = []
            for gdiv in main.select('.g'):
                title_element = gdiv.select_one('h3')
                link_element = gdiv.select_one('a')
                description_element = gdiv.select_one('.VwiC3b')

                res.append({
                    'title': title_element.text if title_element else None,
                    'link': urljoin("https://www.google.com", link_element['href']) if link_element else None,
                    'description': description_element.text if description_element else None,
                })
            return res

        results = extract_results(soup)
        if not results:
            return "No results found!", 404

        first_result = results[0]
        first_link = first_result['link']
        driver.get(first_link)

        try:
            accept_button = wait.until(EC.element_to_be_clickable((By.ID, "btnAcceptLicense")))
            accept_button.click()
        except Exception:
            pass

        table_xpath = '//*[@id="gdvIcd10CoveredCodes1"]/tbody/tr'
        rows = driver.find_elements(By.XPATH, table_xpath)

        table_data = []
        for row in rows:
            cells = row.find_elements(By.TAG_NAME, 'td')
            cell_texts = [cell.text for cell in cells]
            table_data.append(cell_texts)

        matches = [row for row in table_data if icd_code in row]
        if matches:
            return f"ICD-10 Code '{icd_code}' is covered under Medicare guidelines! Matches: {matches}", 200
        else:
            all_codes = [row[0] for row in table_data if row]
            close_matches = get_close_matches(icd_code, all_codes, n=5, cutoff=0.6)
            return f"ICD-10 Code '{icd_code}' is not covered under Medicare guidelines! Close matches: {close_matches}", 200

    finally:
        driver.quit()