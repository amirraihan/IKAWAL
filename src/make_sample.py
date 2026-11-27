"""Jana reman35_contoh.html (pratonton borang Reman 35) daripada sistem_tahanan.html.

Guna:
    python src/build_sistem.py   # pastikan sistem_tahanan.html terkini dahulu
    python src/make_sample.py

Output: <repo>/reman35_contoh.html
"""
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

s = open(os.path.join(ROOT, 'sistem_tahanan.html'), 'r', encoding='utf-8').read()
style = re.search(r'<style>(.*?)</style>', s, re.S).group(1)

PERSON = "ADNAL BIN JAILANI / BAJAU - PHILIPPINES / MALE / 27 YEARS OLD"
SIGN = ("    <p>(MOHD SHAH REZZA BIN ARDIANSHAH)</p>\n"
        "    <p>Deputy Assistant Director Of Immigration</p>\n"
        "    <p>Immigration Malaysia State Of Sabah.</p>\n")

page = """<div class="r35-page">
  <p class="ref">IM.101/S-E/IK/803/4(218)2026</p>
  <p>&nbsp;</p>
  <div class="header-centre">FEDERATION OF MALAYSIA<br>NOTICE<br>SECTION 35 IMMIGRATION ACT 1959/63</div>
  <p>&nbsp;</p>
  <p>TO: __PERSON__</p>
  <p>REMAND NUMBER: 26(2096)BD</p>
  <p>Holder of PHILIPPINES Passport No. : NIL</p>
  <p>&nbsp;</p>
  <p class="long">WHEREAS an arrest report was made againts you, a person reasonably believed to be a person liable to removal from Malaysia under Section 35 of the Immigration Act 1959/63.</p>
  <p>&nbsp;</p>
  <p class="long">And WHEREAS your detention is considered necessary until a decision as to whether an order for your removal should be made.</p>
  <p>&nbsp;</p>
  <p class="long">Now THEREFORE, I, MOHD SHAH REZZA BIN ARDIANSHAH (Deputy Assistant Director Of Immigration, Immigration Malaysia State Of Sabah) by virtue of the power of the Director General Of Immigration vested on me under paragraph 3(3)(b) of the Immigration Act 1959/63 (Act 155), do hereby order that you be detained under section 35 of the Immigration Act 1959/63 (Act 155) at Immigration Depot / Prison in Malaysia.</p>
  <p>Dated in Immigration Depot / Prison Malaysia this: 26th November 2026</p>
  <p>&nbsp;</p>
  <p class="dotline">.</p>
  <p>&nbsp;</p>
__SIGN__
  <p>&nbsp;</p>
  <p>&nbsp;</p>
  <p>To: Officer In Charge</p>
  <p>Immigration Depot / Prison in Malaysia</p>
  <p>Pursuant to the provisions of the above order you are hereby required to received into custody and detain the said</p>
  <p>__PERSON__</p>
  <p>REMAND NUMBER: 26(2096)BD</p>
  <p>Holder of PHILIPPINES Passport No. : NIL</p>
  <p>&nbsp;</p>
  <p>until the decision as to whether an order for his/her removal has been made.</p>
  <p>&nbsp;</p>
  <p>Dated in Immigration Depot / Prison Malaysia this: 26th November 2026</p>
  <p>&nbsp;</p>
  <p class="dotline">.</p>
  <p>&nbsp;</p>
__SIGN__
</div>""".replace("__PERSON__", PERSON).replace("__SIGN__", SIGN)

doc = ('<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Contoh Reman 35</title>'
       '<style>' + style + ' body.app-sample{background:#dfe6ef;padding:24px}'
       '</style></head><body class="app-sample">' + page + '</body></html>')

dst = os.path.join(ROOT, 'reman35_contoh.html')
open(dst, 'w', encoding='utf-8').write(doc)
print('wrote', dst, os.path.getsize(dst), 'bytes')
