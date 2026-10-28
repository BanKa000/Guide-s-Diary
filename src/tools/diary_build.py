# -*- coding: utf-8 -*-
"""
Дневник проводника: сборка мода.

Исходники мода лежат в UTF-8 (папка _src рядом с игрой). Игра читает cp1251, поэтому всё
собирается сюда: S.T.A.L.K.E.R. Call of Pripyat\\gamedata. В _src лежит весь мод: gamedata
можно удалить и собрать заново. Сборку можно запускать после любой правки.

Что делает:
  1. копирует scripts, configs (UTF-8 -> cp1251), textures и spawns (как есть); в сборке
     разработчика ещё dev\\ (в релизе эти файлы из игры удаляются); пустую логику
     отключённых оригинальных квестов пишет по списку gen\\disabled_logic.ltx;
  2. диалоги: стартовые "хабы" (Борода, Кардан, Сыч, Султан, Крим, медики) разбирает
     на приветствие + отдельные темы (actor_dialog), как в ЗП; диалоги заданий генерирует из
     configs\\misc\\diary_jobs.ltx; особые диалоги берёт из gen\\diary_dialogs.xml;
  3. дописывает темы персонажам (character_desc_*.xml) и общим (character_dialogs.xml);
  4. задания tm_zaton.ltx (линии - из diary_jobs.ltx, награды без оповещений);
  5. статики компаса (ui_custom_msgs.xml), предметы, ящики, NPC, броню (gen\\diary_sections.ltx);
  6. торговлю: цены +50% (наёмники x4 сверху), склад по diary_stock.ltx;
  7. проверки; списки для чтения в корне мода: "Диалоги.txt" и "Описания.txt".

Запуск:  python diary_build.py [--dev] [--release]
"""
import os, re, sys, shutil, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.dirname(HERE)                                  # _src
ROOT = os.path.dirname(SRC)                                  # Дневник проводника
GAME = os.environ.get("DIARY_OUT") or os.path.join(ROOT, "S.T.A.L.K.E.R. Call of Pripyat", "gamedata")
PACK = os.environ.get("DIARY_PACK")                          # IX-Ray: папка конфигов пака (приоритет над оригиналом)
GEN = os.path.join(SRC, "gen")                               # входные файлы генератора (UTF-8)
UE = os.path.join(ROOT, "Распакованные файлы", "UEgamedata")  # оригинал ЗП 1.6.00 (cp1251)
PATCH = os.path.join(ROOT, "Распакованные файлы", "patch_1602")  # файлы патчей xpatch_01/02 (xdb.py)

DEV = "--dev" in sys.argv or "--release" not in sys.argv
ENC = "cp1251"

written = []


def rd(path, enc=ENC):
    with open(path, encoding=enc, errors="strict") as f:
        return f.read()


def wr_game(rel, text):
    """Записать файл в игру (cp1251). Символы вне cp1251 - ошибка сборки."""
    path = os.path.join(GAME, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding=ENC, newline="\r\n") as f:
        f.write(text.replace("\r\n", "\n"))
    written.append(rel)


def base(rel):
    return rd(os.path.join(GEN, rel), "utf-8")


def ue(rel):
    """Оригинал игры: сначала из патча 1.6.02 (распакован xdb.py), иначе из 1.6.00."""
    if PACK and os.path.exists(os.path.join(PACK, rel)):
        b = open(os.path.join(PACK, rel), "rb").read()
        try:
            s = b.decode("utf-8")
        except UnicodeDecodeError:
            s = b.decode(ENC)
        return s.replace("\r\n", "\n").encode(ENC, "replace").decode(ENC)
    p = os.path.join(PATCH, rel)
    return rd(p if os.path.exists(p) else os.path.join(UE, rel))


def src(rel):
    return rd(os.path.join(SRC, rel), "utf-8")


# ---------------------------------------------------------------------------------------------
# 1. Скрипты и конфиги из _src
# ---------------------------------------------------------------------------------------------
def walk(top):
    """Файлы папки _src\\<top>, пути относительно неё."""
    for dp, dn, fn in os.walk(os.path.join(SRC, top)):
        for f in fn:
            yield os.path.relpath(os.path.join(dp, f), os.path.join(SRC, top))


def copy_sources():
    for top in ("scripts", "configs"):
        for rel in walk(top):
            wr_game(os.path.join(top, rel), src(os.path.join(top, rel)))
    # текстуры и all.spawn - как есть (копируются, только если изменились)
    for top in ("textures", "spawns"):
        for rel in walk(top):
            a, b = os.path.join(SRC, top, rel), os.path.join(GAME, top, rel)
            if not os.path.exists(b) or open(a, "rb").read() != open(b, "rb").read():
                os.makedirs(os.path.dirname(b), exist_ok=True)
                shutil.copy2(a, b)
            written.append(os.path.join(top, rel))
    # dev\: телепорты, маркер точек, перескок этапов - только в сборке разработчика
    for rel in walk("dev"):
        if DEV:
            wr_game(rel, src(os.path.join("dev", rel)))
        elif os.path.exists(os.path.join(GAME, rel)):
            os.remove(os.path.join(GAME, rel))
    # пустая логика отключённых оригинальных квестов
    kind = None
    for line in src(os.path.join("gen", "disabled_logic.ltx")).split("\n"):
        line = line.split(";")[0].strip()
        m = re.match(r"^\[(.+)\]$", line)
        if m:
            kind = m.group(1)
        elif line:
            wr_game(os.path.join("configs", "scripts", line + ".ltx"),
                    "[logic]\nactive = %s\n\n[%s]\n" % (kind, kind))


# ---------------------------------------------------------------------------------------------
# Описание заданий (diary_jobs.ltx)
# ---------------------------------------------------------------------------------------------
GIVER_CHAR = {
    "bor": "zat_a2_stalker_barmen", "car": "zat_a2_stalker_mechanic", "sul": "zat_b7_bandit_boss_sultan", "kri": "diary_krim",
    "syc": "zat_b30_owl_stalker_trader", "tre": "zat_b22_stalker_medic", "gav": "jup_a6_stalker_barmen",
}
STORY_CHAR = {
    "diary_trader_b5": "diary_trader_b5", "zat_b22_stalker_medic": "zat_b22_stalker_medic",
    "zat_b30_owl_stalker_trader_id": "zat_b30_owl_stalker_trader",
}


def read_jobs():
    text = src(os.path.join("configs", "misc", "diary_jobs.ltx"))
    order, jobs, cur = [], {}, None
    for line in text.split("\n"):
        line = line.split(";")[0].strip()
        if not line:
            continue
        m = re.match(r"^\[([^\]]+)\]", line)
        if m:
            cur = m.group(1)
            if cur != "list":
                jobs[cur] = {}
            continue
        if cur == "list":
            order.append(line)
        elif cur is not None and "=" in line:
            k, v = line.split("=", 1)
            jobs[cur][k.strip()] = v.strip()
    return order, jobs


# ---------------------------------------------------------------------------------------------
# 2. Диалоги
# ---------------------------------------------------------------------------------------------
HUBS = ["diary_zat_barmen_start", "diary_zat_medic_start", "diary_zat_mechanic_start",
        "diary_zat_trader_start", "diary_krim_start", "diary_sultan_start"]


def parse_phrases(body):
    out = {}
    order = []
    for m in re.finditer(r'<phrase id="(\d+)">(.*?)</phrase>', body, re.S):
        pid, inner = m.group(1), m.group(2)
        nexts = re.findall(r"<next>(\d+)</next>", inner)
        rest = re.sub(r"\s*<next>\d+</next>", "", inner)
        out[pid] = {"inner": rest.strip(), "next": nexts}
        order.append(pid)
    return out, order


def phrase_xml(pid, ph, nexts, indent="            "):
    lines = [indent + '<phrase id="%s">' % pid]
    for l in ph["inner"].split("\n"):
        l = l.strip()
        if l:
            lines.append(indent + "    " + l)
    for n in nexts:
        lines.append(indent + "    <next>%s</next>" % n)
    lines.append(indent + "</phrase>")
    return "\n".join(lines)


def convert_hub(did, body):
    """Хаб -> (стартовый диалог-приветствие, [(id темы, xml темы)])"""
    ph, order = parse_phrases(body)
    root = ph["0"]
    hub = set(root["next"])
    topics = []
    for t in root["next"]:
        if int(t) >= 9000 or t in ("98", "99"):
            continue
        # поддерево темы; ссылки назад в хаб и на 98/99 отрезаются - тема заканчивается
        seen, queue = [], [t]
        while queue:
            p = queue.pop(0)
            if p in seen or p not in ph:
                continue
            seen.append(p)
            for n in ph[p]["next"]:
                if n not in hub and n not in ("0", "98", "99") and int(n) < 9000:
                    queue.append(n)
        tid = "%s_%s" % (did, t)
        conds = re.findall(r"<(precondition|has_info|dont_has_info)>([^<]+)</\1>", ph[t]["inner"])
        lines = ['    <dialog id="%s">' % tid]
        for tag, val in conds:
            lines.append("        <%s>%s</%s>" % (tag, val, tag))
        lines.append("        <phrase_list>")
        for p in seen:
            nexts = [n for n in ph[p]["next"] if n in seen and n != t]
            pid = "0" if p == t else p
            lines.append(phrase_xml(pid, ph[p], ["0" if n == t else n for n in nexts]))
        lines.append("        </phrase_list>")
        lines.append("    </dialog>")
        topics.append((tid, "\n".join(lines)))
    start = ['    <dialog id="%s">' % did, "        <phrase_list>", phrase_xml("0", root, []),
             "        </phrase_list>", "    </dialog>"]
    return "\n".join(start), topics


def dlg(did, conds, phrases):
    """phrases: [(id, text, [теги], [next])]"""
    out = ['    <dialog id="%s">' % did]
    for c in conds:
        out.append("        <precondition>%s</precondition>" % c)
    out.append("        <phrase_list>")
    for pid, text, tags, nexts in phrases:
        out.append('            <phrase id="%s">' % pid)
        out.append("                <text>%s</text>" % text)
        for t in tags:
            out.append("                " + t)
        for n in nexts:
            out.append("                <next>%s</next>" % n)
        out.append("            </phrase>")
    out.append("        </phrase_list>")
    out.append("    </dialog>")
    return "\n".join(out)


def text_ids():
    """Все id строк мода (чтобы у задания могли быть свои реплики _ask, _yes, _no)."""
    return set(re.findall(r'<string id="([^"]+)"', src(os.path.join("configs", "text", "rus", "st_zz_diary.xml"))))


N6_NAMES = ["Кардану", "Сычу", "Султану", "Криму"]    # биты 1,2,4,8 (diary_debt_c/s, diary_deb_1/2)


def n6_reply(mask):
    """id реплики Бороды по набору закрытых долгов (бит 1 Кардан, 2 Сыч, 4 Султан, 8 Крим)."""
    if mask == 15:
        return "dj_n6_r_all"
    if mask == 0:
        return "dj_n6_r_none"
    c = not mask & 1
    b = (mask & 6) != 6
    k = not mask & 8
    return "dj_n6_r_" + ("k" if k else "") + ("c" if c else "") + ("b" if b else "")


def n6_phrases(sec, A, accept=False):
    """Разговор перед уходом: ответ Лазаря зависит от того, кому закрыты долги; Борода отвечает по группам."""
    ph = [("0", sec + "_rep", [], ["1"]),
          ("1", "dj_n6_q", ["<action>%sa_n6</action>" % A] if accept else [], ["a%d" % m for m in range(16)])]
    for m in range(16):
        txt = "dj_n6_a_all" if m == 15 else "dj_n6_a_none" if m == 0 else "dj_n6_a_%d" % m
        k = 1 if bin(m).count("1") >= 2 else 2
        ph.append(("a%d" % m, txt, ["<precondition>%sn6_m%d</precondition>" % (A, m)], ["r%d" % m]))
        ph.append(("r%d" % m, n6_reply(m), ["<action>%sd_n6_%d</action>" % (A, k)], []))
    return ph


def job_dialogs(order, jobs):
    """-> (xml, {персонаж: [id диалогов]}, {id: True} общих)"""
    xml, attach = [], {}
    TX = text_ids()

    def add(ch, d):
        attach.setdefault(ch, []).append(d)

    for sec in order:
        q = jobs[sec]
        jid = sec[3:]
        giver = GIVER_CHAR[q["giver"]]
        A = "dialogs_diary."
        # предложение
        if sec == "dj_n6":
            # по Диалоги.txt (main_14) отдельного предложения нет: разговор о долгах сразу и закрывает задание
            xml.append(dlg(sec + "_offer", [A + "o_" + jid], n6_phrases(sec, A, True)))
        elif sec in ("dj_n1", "dj_n5"):
            # по Диалоги.txt отдельного предложения нет: n1 берётся в разговоре main_3, n5 - в ветке "Помогу" отчёта n4
            pass
        else:
          # реплика заказчика после согласия (_ok) и вторая отговорка (_no2) - необязательные
          has_ok = sec + "_ok" in TX
          has_no2 = sec + "_no2" in TX
          ph_offer = [
            ("0", sec + "_ask" if sec + "_ask" in TX else "dj_ask", [], ["1"]),
            ("1", sec + "_offer", [], ["2", "3"] + (["5"] if has_no2 else [])),
            ("2", sec + "_yes" if sec + "_yes" in TX else "dj_accept", ["<action>%sa_%s</action>" % (A, jid)], ["4"] if has_ok else []),
            ("3", sec + "_no" if sec + "_no" in TX else "dj_later", [], []),
          ]
          if has_ok:
            ph_offer.append(("4", sec + "_ok", [], []))
          if has_no2:
            ph_offer.append(("5", sec + "_no2", [], []))
          xml.append(dlg(sec + "_offer", [A + "o_" + jid], ph_offer))
        if sec not in ("dj_n1", "dj_n5"):
            add(giver, sec + "_offer")
        # отчёт (у n6 разговор один - main_14, он же закрывает задание)
        if q.get("no_report") != "true" and sec != "dj_n6":
            rep_char = GIVER_CHAR[q["report_to"]] if q.get("report_to") else giver
            choices = [c.strip() for c in q["choices"].split(",")] if q.get("choices") else None
            if sec == "dj_n4":
                xml.append(dlg(sec + "_report", [A + "r_" + jid], [
                    ("0", sec + "_rep", [], ["1"]),
                    ("1", "dj_n4_help_q", [], ["a1", "a2"]),
                    ("a1", "dj_n4_help_yes_a", [], ["r1"]),
                    ("r1", "dj_n4_help_yes_r", ["<action>%sn4_yes</action>" % A], []),
                    ("a2", "dj_n4_help_no_a", [], ["r2"]),
                    ("r2", "dj_n4_help_no_r", ["<action>%sn4_no</action>" % A], []),
                ]))
            elif not choices:
                xml.append(dlg(sec + "_report", [A + "r_" + jid], [
                    ("0", sec + "_rep", [], ["1"]),
                    ("1", sec + "_done", ["<action>%sd_%s</action>" % (A, jid)], []),
                ]))
            elif sec == "dj_n6":
                xml.append(dlg(sec + "_report", [A + "r_" + jid], n6_phrases(sec, A)))
            else:
                ph = [("0", sec + "_rep", [], ["1"]),
                      ("1", sec + "_q" if sec + "_q" in TX else "dj_report_q", [], ["c%d" % k for k in range(1, len(choices) + 1)])]
                for k in range(1, len(choices) + 1):
                    ph.append(("c%d" % k, "%s_c%d_a" % (sec, k - 1),
                               ["<precondition>%sc_%s_%d</precondition>" % (A, jid, k)], ["r%d" % k]))
                    ph.append(("r%d" % k, "%s_c%d_r" % (sec, k - 1),
                               ["<action>%sd_%s_%d</action>" % (A, jid, k)], []))
                xml.append(dlg(sec + "_report", [A + "r_" + jid], ph))
            add(rep_char, sec + "_report")
        # выкуп вместо задания
        if q.get("alt_pay"):
            xml.append(dlg(sec + "_alt", [A + "l_" + jid], [
                ("0", sec + "_alt_a", [], ["1"]),
                ("1", sec + "_alt_r", ["<action>%sp_%s</action>" % (A, jid)], []),
            ]))
            add(giver, sec + "_alt")
        # доставка получателю
        if q.get("kind") == "deliver":
            xml.append(dlg(sec + "_deliver", [A + "dlv_here_" + jid], [
                ("0", sec + "_dlv_a", [], ["1"]),
                ("1", sec + "_dlv_r", ["<action>%sdlv_%s</action>" % (A, jid)], []),
            ]))
            add(STORY_CHAR[q["to"]], sec + "_deliver")
    return "\n".join(xml), attach


SPEECH = {}     # "диалог|фраза" -> [(id персонажа, id текста), ...] (для Диалоги.txt)


def speakers():
    """id персонажа -> (строка имени, иконка) по всем описаниям персонажей мода."""
    res = {}
    texts = [src(os.path.join("gen", "diary_characters.xml"))]
    for f in ("character_desc_zaton.xml", "character_desc_jupiter.xml"):
        texts.append(base(os.path.join("configs", "gameplay", f)))
    for t in texts:
        for m in re.finditer(r'<specific_character id="([^"]+)".*?</specific_character>', t, re.S):
            name = re.search(r"<name>\s*(.*?)\s*</name>", m.group(0))
            icon = re.search(r"<icon>\s*(.*?)\s*</icon>", m.group(0))
            if name and icon:
                res[m.group(1)] = (name.group(1), icon.group(1))
    return res


def build_speech(extra):
    """<say who="персонаж">текст</say> во фразах -> пустая фраза + dialogs_diary.say; таблица SPEECH
    дописывается в конец dialogs_diary.script в игре."""
    who_info = speakers()
    rows = []

    def phrase(m, did):
        body = m.group(2)
        says = re.findall(r'<say who="([^"]+)">\s*([^<]+?)\s*</say>', body)
        if not says:
            return m.group(0)
        lines = []
        for who, sid in says:
            if who not in who_info:
                raise SystemExit("! <say who=\"%s\"> в диалоге %s: нет такого персонажа" % (who, did))
            name, icon = who_info[who]
            lines.append('{"%s", "%s", "%s"}' % (name, icon, sid))
        SPEECH[did + "|" + m.group(1)] = says
        rows.append('\t["%s|%s"] = {%s},' % (did, m.group(1), ", ".join(lines)))
        body = re.sub(r'\s*<say who="[^"]+">[^<]*</say>', "", body)
        return '<phrase id="%s"><text></text><action>dialogs_diary.say</action>%s</phrase>' % (m.group(1), body)

    def dialog(m):
        did = m.group(1)
        return re.sub(r'<phrase id="([^"]+)">(.*?)</phrase>', lambda pm: phrase(pm, did), m.group(0), flags=re.S)

    extra = re.sub(r'<dialog id="([^"]+)"[^>]*>.*?</dialog>', dialog, extra, flags=re.S)
    rel = os.path.join("scripts", "dialogs_diary.script")
    wr_game(rel, src(rel).rstrip() + "\n\n--' сгенерировано сборщиком из <say> в gen\\diary_dialogs.xml\nSPEECH = {\n"
            + "\n".join(rows) + "\n}\n")
    return extra


def build_dialogs(order, jobs):
    text = base(os.path.join("configs", "gameplay", "dialogs_zaton.xml"))
    attach = {}
    # хабы -> приветствие + темы
    for did in HUBS:
        m = re.search(r'    <dialog id="%s">.*?</dialog>' % did, text, re.S)
        start, topics = convert_hub(did, m.group(0))
        text = text.replace(m.group(0), start + "\n" + "\n".join(t[1] for t in topics))
        attach[did] = [t[0] for t in topics]
    # функции диалогов переехали в dialogs_diary.script
    text = text.replace("diary_zat.", "dialogs_diary.").replace("diary_jobs.", "dialogs_diary.")
    # диалоги заданий и особые
    jx, jattach = job_dialogs(order, jobs)
    extra = src(os.path.join("gen", "diary_dialogs.xml"))
    extra_attach = {}
    for m in re.finditer(r'<dialog id="([^"]+)" attach="([^"]+)">', extra):
        for ch in m.group(2).split(","):
            extra_attach.setdefault(ch.strip(), []).append(m.group(1))
    extra = build_speech(extra)
    extra_body = re.sub(r'<dialog id="([^"]+)" attach="[^"]+">', r'<dialog id="\1">', extra)
    extra_body = extra_body[extra_body.index("<game_dialogs>") + len("<game_dialogs>"):extra_body.index("</game_dialogs>")]
    gen = "\n    <!-- ===== Дневник проводника: задания линий (diary_build.py из diary_jobs.ltx) ===== -->\n" + jx + \
          "\n    <!-- ===== Дневник проводника: особые диалоги (gen\\diary_dialogs.xml) ===== -->" + extra_body
    text = text.replace("</game_dialogs>", gen + "\n</game_dialogs>")
    # основная линия Бороды из Диалоги.txt (gen\story_dialogs.xml): диалоги с теми же id подменяются целиком
    sd = src(os.path.join("gen", "story_dialogs.xml"))
    for m in re.finditer(r'    <dialog id="([^"]+)"( attach="([^"]+)")?>.*?</dialog>', sd, re.S):
        did, block = m.group(1), re.sub(r' attach="[^"]+"', "", m.group(0), count=1)
        old = re.search(r'    <dialog id="%s">.*?</dialog>' % re.escape(did), text, re.S)
        if old is not None:
            text = text.replace(old.group(0), block.replace("\r\n", "\n"), 1)
        else:
            text = text.replace("</game_dialogs>", block + "\n</game_dialogs>")
            for ch in (m.group(3) or "").split(","):
                if ch.strip():
                    extra_attach.setdefault(ch.strip(), []).append(did)
    wr_game(os.path.join("configs", "gameplay", "dialogs_zaton.xml"), text)
    return attach, jattach, extra_attach


# ---------------------------------------------------------------------------------------------
# 3. Персонажи
# ---------------------------------------------------------------------------------------------
def attach_dialogs(text, char_id, dialogs):
    m = re.search(r'(<specific_character id="%s"[^>]*>)(.*?)(</specific_character>)' % re.escape(char_id), text, re.S)
    if m is None:
        return text, False
    body = m.group(2)
    add = "".join("\t\t<actor_dialog>%s</actor_dialog>\n" % d for d in dialogs if "<actor_dialog>%s<" % d not in body)
    if "<actor_dialog>actor_break_dialog</actor_dialog>" not in body:
        add += "\t\t<actor_dialog>actor_break_dialog</actor_dialog>\n"
    text = text[:m.start(3)] + add + "\t" + text[m.start(3):]
    return text, True


# Стартовое снаряжение Лазаря - сразу в профиле actor (движок выдаёт его при создании героя)
ACTOR_SUPPLIES = [
    "device_torch", "wpn_binoc", "wpn_knife", "detector_simple", "novice_outfit",
    "wpn_colt1911", "ammo_11.43x23_fmj = 1",      # пачка - 50 патронов
    "bandage = 2", "antirad = 1", "medkit = 4",
    "bread = 1", "kolbasa = 1", "conserva = 2",
]


def build_actor():
    rel = os.path.join("configs", "gameplay", "character_desc_general.xml")
    text = ue(rel)
    m = re.search(r'(<specific_character id="actor"[^>]*>.*?<supplies>)(.*?)(</supplies>)', text, re.S)
    if m is None:
        raise SystemExit("character_desc_general.xml: не найден профиль actor")
    body = "\n\t\t\t[spawn] \\n\n" + "".join("\t\t\t%s \\n\n" % s for s in ACTOR_SUPPLIES) + "    "
    wr_game(rel, text[:m.start(2)] + body + text[m.end(2):])


def build_profiles(chars_text):
    """npc_profile.xml: character_profile в секции NPC ссылается на <character id>, а не на
    specific_character. Без профиля - вылет "item not found, id ..." при спавне. Профиль добавляется
    каждому персонажу мода (diary_*), у которого его ещё нет."""
    rel = os.path.join("configs", "gameplay", "npc_profile.xml")
    text = base(rel)
    text = re.sub(r"<\?xml[^>]*\?>", '<?xml version="1.0" encoding="windows-1251"?>', text, count=1)
    have = set(re.findall(r'<character id="([^"]+)"', text))
    add = ""
    for cid in re.findall(r'<specific_character id="(diary_[^"]+)"', chars_text):
        if cid not in have:
            add += '\t<character id="%s">\n\t\t<class>%s</class>\n\t</character>\n' % (cid, cid)
            have.add(cid)
    i = text.rindex("</xml>")
    wr_game(rel, text[:i] + add + text[i:])


def build_characters(hub_attach, jattach, extra_attach):
    zat = base(os.path.join("configs", "gameplay", "character_desc_zaton.xml"))
    jup = base(os.path.join("configs", "gameplay", "character_desc_jupiter.xml"))
    app = src(os.path.join("gen", "diary_characters.xml"))
    # В конце файла после комментариев движок этих персонажей не зарегистрировал (вылет
    # "item not found, id diary_dj_sci"), поэтому вставляем без комментариев и перед diary_krim,
    # рядом с персонажами, которые точно загружаются.
    app = re.sub(r"(?s)[ \t]*<!--.*?-->[ \t]*\r?\n?", "", app).strip("\n")
    anchor = '  <specific_character id="diary_krim"'
    if anchor not in zat:
        raise SystemExit("character_desc_zaton.xml: не найден diary_krim для вставки персонажей заданий")
    zat = zat.replace(anchor, app + "\n\n" + anchor, 1)
    per_char = {}
    # темы хабов - всем, у кого этот хаб стартовый
    for hub, topics in hub_attach.items():
        for doc in (zat, jup):
            for m in re.finditer(r'<specific_character id="([^"]+)"[^>]*>(?:(?!</specific_character>).)*?<start_dialog>%s</start_dialog>' % hub, doc, re.S):
                per_char.setdefault(m.group(1), []).extend(topics)
    for src_map in (jattach, extra_attach):
        for ch, ds in src_map.items():
            if ch != "generic":
                per_char.setdefault(ch, []).extend(ds)
    missing = []
    for ch, ds in per_char.items():
        zat, ok = attach_dialogs(zat, ch, ds)
        if not ok:
            jup, ok = attach_dialogs(jup, ch, ds)
        if not ok:
            missing.append(ch)
    wr_game(os.path.join("configs", "gameplay", "character_desc_zaton.xml"), zat)
    wr_game(os.path.join("configs", "gameplay", "character_desc_jupiter.xml"), jup)
    build_profiles(zat + jup)
    # общие темы - всем через character_dialogs.xml
    cd = ue(os.path.join("configs", "gameplay", "character_dialogs.xml"))
    gen = "".join("<actor_dialog>%s</actor_dialog>\n" % d for d in extra_attach.get("generic", []))
    gen = "\n<actor_dialog>dj_k2_ransom</actor_dialog>\n" + gen
    cd = cd.replace("<actor_dialog>actor_break_dialog</actor_dialog>", gen + "\n<actor_dialog>actor_break_dialog</actor_dialog>")
    wr_game(os.path.join("configs", "gameplay", "character_dialogs.xml"), cd)
    return missing


# ---------------------------------------------------------------------------------------------
# 4. Задания (tm_zaton.ltx)
# ---------------------------------------------------------------------------------------------
STORY_TASK_PATCH = {
    "diary_q10": ("title = {+diary_decoded} diary_q10_name_2, diary_q10_name\n"
                  "descr = {+diary_decoded} diary_q10_text_2, diary_q10_text\n"
                  "condlist_0 = {+diary_cipher_read} complete"),
}


def build_tasks(order, jobs):
    text = base(os.path.join("configs", "misc", "tm_zaton.ltx"))
    # старые секции заданий линий убираем, генерируем заново
    i = text.find("; Дневник проводника: задания линий Затона")
    if i >= 0:
        text = text[:i]
    # награды за сюжет - без оповещения "получено" (правка 1)
    text = re.sub(r"(?m)^reward_money\s*=\s*(\d+)\s*$", r"on_complete = %=diary_give_money(\1)%", text)
    for sec, body in STORY_TASK_PATCH.items():
        m = re.search(r"(\[%s\]\n(?:[^\[]*?\n)?)(title\s*=.*?\n)(descr\s*=.*?\n)(condlist_0\s*=.*?\n)" % sec, text, re.S)
        if m:
            text = text[:m.start(2)] + body + "\n" + text[m.end(4):]
    # цель на карте КПК и кнопка "показать на карте": task_functor.diary_target (diary_compass)
    text = re.sub(r"(?m)^(\[diary_[qd]\d+\]\n)(?!target_functor)", r"\1target_functor = diary_target\n", text)
    out = [text.rstrip(), "", "; Дневник проводника: задания линий (diary_build.py из diary_jobs.ltx)"]
    for n, sec in enumerate(order):
        q = jobs[sec]
        cond = "{+%s_done} complete" % sec
        if sec in ("dj_s9", "dj_s10", "dj_k8"):
            cond = "{+%s_cancelled} fail, {+%s_done} complete" % (sec, sec)
        out += ["[%s]" % sec, "prior = %d" % (200 + n), "storyline = false",
                "title = %s_name" % sec, "descr = %s_text" % sec, "condlist_0 = " + cond,
                "target_functor = diary_target", "dont_send_update_news = true", ""]
    wr_game(os.path.join("configs", "misc", "tm_zaton.ltx"), "\n".join(out))


# ---------------------------------------------------------------------------------------------
# 5. Интерфейс, предметы, NPC
# ---------------------------------------------------------------------------------------------
def compass_xml():
    C = "225\" g=\"215\" b=\"190"
    out = ["\t<!-- Diary: kompas (diary_compass.script), kompaktnyj 168x40 -->",
           '\t<diary_cmp_bg x="428" y="4" width="168" height="40" stretch="1">',
           '\t\t<texture a="130">intro\\intro_back</texture>', "\t</diary_cmp_bg>",
           '\t<diary_cmp_line x="432" y="22" width="160" height="1" stretch="1">',
           '\t\t<texture r="225" g="215" b="190" a="140">ui_minimap_point</texture>', "\t</diary_cmp_line>",
           '\t<diary_cmp_tick x="510" y="20" width="4" height="4" stretch="1">',
           "\t\t<texture>ui_minimap_point</texture>", "\t</diary_cmp_tick>"]
    for i in range(1, 9):
        out += ['\t<diary_cmp_l%d x="0" y="6" width="30" height="16">' % i,
                '\t\t<text align="c" font="letterica16" r="%s" a="230"/>' % C, "\t</diary_cmp_l%d>" % i]
    for i in range(1, 13):
        out += ['\t<diary_cmp_d%d x="0" y="28" width="6" height="6" stretch="1">' % i,
                '\t\t<texture r="150" g="150" b="150" a="230">ui_minimap_point</texture>', "\t</diary_cmp_d%d>" % i]
    for i in range(1, 13):
        out += ['\t<diary_cmp_e%d x="0" y="28" width="6" height="6" stretch="1">' % i,
                '\t\t<texture r="255" g="40" b="40" a="230">ui_minimap_point</texture>', "\t</diary_cmp_e%d>" % i]
    for i in range(1, 17):
        out += ['\t<diary_cmp_m%d x="0" y="24" width="14" height="14" stretch="1">' % i,
                "\t\t<texture>ui_inGame2_PDA_icon_Stalker_VIP</texture>", "\t</diary_cmp_m%d>" % i]
    out += ['\t<diary_cmp_task x="362" y="44" width="300" height="16" complex_mode="0">',
            '\t\t<text align="c" font="letterica16" r="240" g="217" b="182" a="220"/>', "\t</diary_cmp_task>"]
    return "\n".join(out)


WIDE = 0.8          # 16:9: та же картинка занимает 819 из 1024 единиц по ширине
WIDE_LEFT = 102     # отступ фона КПК слева в 16:9 (как в оригинальном pda_16.xml)


def widescreen(text, absolute, stretch_tags):
    """Версия *_16.xml из 4:3: x и width по горизонтали x0.8, у текстур stretch.
    absolute - элементы верхнего уровня в координатах экрана (pda.xml), иначе - от фона КПК.
    main / main_wnd верхнего уровня и hint_wnd остаются как в оригинале."""
    out = []
    depth = 0
    keep = 0            # внутри hint_wnd - без изменений
    for tok in re.split(r"(<[^>]+>)", text):
        if not tok.startswith("<") or tok.startswith("<!--") or tok.startswith("<?"):
            out.append(tok)
            continue
        if tok.startswith("</"):
            depth -= 1
            if keep and depth < keep:
                keep = 0
            out.append(tok)
            continue
        name = re.match(r"<([\w]+)", tok).group(1)
        selfclose = tok.endswith("/>")
        top = depth == 1
        if name == "hint_wnd" and top:
            keep = depth + 1 if not selfclose else 0
        if not keep and not (top and name in ("main", "main_wnd")):
            def sx(m):
                v = float(m.group(2)) * WIDE
                if m.group(1) == "x" and top and absolute:
                    v += WIDE_LEFT
                return '%s="%g"' % (m.group(1), round(v, 1))
            tok = re.sub(r'\b(x|width)="(-?[\d.]+)"', sx, tok)
            if name == "background_static" and top and absolute:
                tok = re.sub(r'\bx="[\d.]+"', 'x="%d"' % WIDE_LEFT, tok)
                tok = re.sub(r'\bwidth="[\d.]+"', 'width="819"', tok)
            # stretch - только там, где он есть в оригинальном *_16.xml: рамкам (InitFrameLine) он запрещён
            if 'stretch="' not in tok and name in stretch_tags:
                tok = tok[:-2].rstrip() + ' stretch="1"/>' if selfclose else tok[:-1].rstrip() + ' stretch="1">'
        out.append(tok)
        if not selfclose:
            depth += 1
    return "".join(out)


def build_ui():
    rel = os.path.join("configs", "ui", "ui_custom_msgs.xml")
    text = base(rel)
    i = text.index("\t<!-- Diary: kompas")
    j = text.index("</diary_cmp_task>") + len("</diary_cmp_task>")
    text = text[:i] + compass_xml() + text[j:]
    wr_game(rel, text)
    # КПК = блокнот Лазаря: 4:3 лежат в _src\configs\ui (копируются), 16:9 строим из них
    for name, absolute in (("pda", True), ("pda_tasks", False), ("pda_logs", False)):
        src_text = src(os.path.join("configs", "ui", name + ".xml"))
        orig16 = ue(os.path.join("configs", "ui", name + "_16.xml"))
        tags = set(re.findall(r'<(\w+)[^>]*\bstretch="1"', orig16))
        wr_game(os.path.join("configs", "ui", name + "_16.xml"), widescreen(src_text, absolute, tags))


def replace_block(text, start_marker, new_block):
    i = text.find(start_marker)
    if i < 0:
        return text.rstrip() + "\n" + new_block
    return text[:i].rstrip() + "\n" + new_block


def sections(target):
    """Кусок gen\\diary_sections.ltx для файла игры target (от строки "; >>> target" до следующей такой)."""
    parts = re.split(r"(?m)^; >>> (.+)$", src(os.path.join("gen", "diary_sections.ltx")))
    for i in range(1, len(parts), 2):
        if parts[i].strip() == target:
            return parts[i + 1].strip("\n") + "\n"
    raise KeyError(target)


def build_items():
    rel = os.path.join("configs", "misc", "quest_items.ltx")
    text = base(rel)
    text = replace_block(text, "; Diary jobs items", sections(r"configs\misc\quest_items.ltx"))
    wr_game(rel, text)

    rel = os.path.join("configs", "misc", "devices.ltx")
    text = base(rel)
    text = replace_block(text, "[diary_rucksack_box]", sections(r"configs\misc\devices.ltx"))
    wr_game(rel, text)

    rel = os.path.join("configs", "misc", "outfit.ltx")
    wr_game(rel, ue(rel).rstrip() + "\n" + sections(r"configs\misc\outfit.ltx"))

    rel = os.path.join("configs", "creatures", "spawn_sections_zaton.ltx")
    text = base(rel)
    text = replace_block(text, "[diary_krim]:stalker", sections(r"configs\creatures\spawn_sections_zaton.ltx"))
    wr_game(rel, text)

    # отряды: разведчик и мародёры нейтральны (с ними говорят), остальное - squad_descr_diary.ltx
    rel = os.path.join("configs", "misc", "squad_descr_zaton.ltx")
    text = base(rel)
    text = re.sub(r"(\[dj_scout\]:online_offline_group\nfaction = stalker\nrelationship = )enemy", r"\1neutral", text)
    text = re.sub(r"(\[dj_marauders\]:online_offline_group\nfaction = bandit\nrelationship = )enemy", r"\1neutral", text)
    text = text.replace("[dj_ambush_bandits]", "; было: засада бандитов в \"Слухах\" (теперь dj_ambush_mercs)\n[dj_ambush_bandits]")
    wr_game(rel, text)
    rel = os.path.join("configs", "misc", "squad_descr.ltx")
    text = ue(rel).replace('#include "squad_descr_underpass.ltx"', '#include "squad_descr_underpass.ltx"\n#include "squad_descr_diary.ltx"')
    wr_game(rel, text)

    # меньше лута с NPC (правка 6): количество патронов и прочего в трупах - вдвое меньше
    rel = os.path.join("configs", "misc", "death_items_count.ltx")
    text = ue(rel)

    def half(m):
        nums = [max(1, int(x) // 2) for x in re.findall(r"\d+", m.group(2))]
        return m.group(1) + ", ".join(str(n) for n in nums)
    text = re.sub(r"(?m)^(\S+\s*=\s*)(\d+(?:\s*,\s*\d+)?)\s*$", half, text)
    wr_game(rel, "; Дневник проводника: количество вещей в трупах уменьшено вдвое (правка 6)\n" + text)

    rel = os.path.join("configs", "misc", "death_items_by_communities.ltx")
    text = ue(rel)

    def less(m):
        return "%s%.2f" % (m.group(1), float(m.group(2)) * 0.6)
    text = re.sub(r"(?m)^(\S+\s*=\s*)(\d*\.?\d+)\s*$", less, text)
    wr_game(rel, "; Дневник проводника: вероятность вещей в трупах x0.6 (правка 6)\n" + text)


# ---------------------------------------------------------------------------------------------
# 6. Торговля
# ---------------------------------------------------------------------------------------------
NEW_OUTFITS = []


def scale_sell(text, mult):
    """Цены продажи игроку: все секции *sell* x mult"""
    out, cur = [], ""
    for line in text.split("\n"):
        m = re.match(r"^\[([^\]]+)\]", line)
        if m:
            cur = m.group(1)
        elif "sell" in cur and not cur.startswith("discount"):
            mm = re.match(r"^(\S+\s*=\s*)([\d.]+)\s*,\s*([\d.]+)(.*)$", line)
            if mm:
                line = "%s%g, %g%s" % (mm.group(1), float(mm.group(2)) * mult, float(mm.group(3)) * mult, mm.group(4))
        out.append(line)
    return "\n".join(out)


def trade_file(orig_rel, mult, discounts=None, note=""):
    text = ue(orig_rel)
    # склад ведёт diary_trade (diary_stock.ltx): buy_supplies убираем, чтобы движок не досыпал своё
    text = re.sub(r"(?m)^buy_supplies\s*=.*$", "; buy_supplies - склад ведёт diary_trade.script (diary_stock.ltx)", text)
    if discounts:
        if re.search(r"(?m)^discounts\s*=", text):
            text = re.sub(r"(?m)^discounts\s*=.*$", "discounts = " + discounts, text)
        else:
            text = text.replace("[trader]\n", "[trader]\ndiscounts = %s\n" % discounts, 1)
        text = text + "\n\n[diary_discount_20]\nbuy = 1\nsell = 0.8\n\n[diary_no_discount]\nbuy = 1\nsell = 1\n"
    # новая броня: продаётся и покупается
    add_sell = "".join("%s = 1, 2.2\n" % o for o in NEW_OUTFITS)
    add_buy = "".join("%s = 0.5, 0.3\n" % o for o in NEW_OUTFITS)
    text = re.sub(r"(\[trade_generic_sell\][^\n]*\n)", r"\1" + add_sell, text, count=1)
    text = re.sub(r"(\[trade_generic_buy\][^\n]*\n)", r"\1" + add_buy, text, count=1)
    text = scale_sell(text, mult)
    return "; Дневник проводника: %s Цены продажи x%g от оригинала.\n" % (note, mult) + text


def balance_num(section, line):
    """Число из diary_balance.ltx (баланс - только в конфиге)."""
    text = src(os.path.join("configs", "misc", "diary_balance.ltx"))
    m = re.search(r"(?ms)^\[%s\].*?^%s\s*=\s*([0-9.]+)" % (re.escape(section), re.escape(line)), text)
    if m is None:
        raise SystemExit("diary_balance.ltx: нет [%s] %s" % (section, line))
    return float(m.group(1))


def build_trade():
    T = os.path.join("configs", "misc", "trade")
    norm = balance_num("prices", "upgrade_mult")
    merc = norm * balance_num("prices", "merc_mult")
    wr_game(os.path.join(T, "trade_zat_b30_stalker_trader.ltx"),
            trade_file(os.path.join(T, "trade_zat_b30_stalker_trader.ltx"), norm,
                       "{+diary_syc_t4} diary_discount_20, diary_no_discount", "Сыч; скидка 20% после линии Сыча."))
    wr_game(os.path.join(T, "trade_zat_a2_barmen.ltx"),
            trade_file(os.path.join(T, "trade_zat_a2_barmen.ltx"), norm, note="Борода."))
    wr_game(os.path.join(T, "trade_zat_b22_stalker_medic.ltx"),
            trade_file(os.path.join(T, "trade_zat_b22_stalker_medic.ltx"), norm, note="Тремор."))
    wr_game(os.path.join(T, "trade_diary_bandit.ltx"),
            trade_file(os.path.join(T, "trade_zat_b30_stalker_trader.ltx"), norm,
                       "diary_no_discount", "торговец бандитов (Лесничество)."))
    wr_game(os.path.join(T, "trade_diary_merc.ltx"),
            trade_file(os.path.join(T, "trade_zat_b30_stalker_trader.ltx"), merc,
                       "diary_no_discount", "торговец наёмников (Цеха): x%g к обычной цене." % (merc / norm)))
    wr_game(os.path.join(T, "trade_diary_bandit_medic.ltx"),
            trade_file(os.path.join(T, "trade_zat_b22_stalker_medic.ltx"), norm, note="медик бандитов."))
    wr_game(os.path.join(T, "trade_diary_merc_medic.ltx"),
            trade_file(os.path.join(T, "trade_jup_b202_stalker_medic.ltx"), merc, note="медик наёмников: x%g к обычной цене, как у их торговца." % (merc / norm)))
    # Гаваец: пока склад пуст (после 3 дней и до договора с ворами) продаёт только еду - даже то, что купил у игрока
    gav = trade_file(os.path.join(T, "trade_jup_b202_stalker_barmen.ltx"), norm, note="Гаваец.")
    sell = re.search(r"\[trade_generic_sell\][^\n]*\n(.*?)(?=\n\[|\Z)", gav, re.S).group(1)
    food = [l for l in sell.split("\n") if re.match(r"^(bread|kolbasa|conserva|vodka|energy_drink)\s*=", l)]
    gav = re.sub(r"(?m)^sell_condition\s*=.*$", "sell_condition = {+diary_gav_stopped -diary_gav_t2} diary_gav_sell_stop, trade_generic_sell", gav)
    gav += "\n\n[diary_gav_sell_stop]\n" + "\n".join(food) + "\n"
    wr_game(os.path.join(T, "trade_jup_b202_stalker_barmen.ltx"), gav)
    wr_game(os.path.join(T, "trade_jup_b202_stalker_medic.ltx"),
            trade_file(os.path.join(T, "trade_jup_b202_stalker_medic.ltx"), norm, note="Костоправ."))
    # все остальные торговцы игры - тоже +50%
    for f in ("trade_generic.ltx", "trade_barmen_all.ltx", "trade_jup_b6_scientist_nuclear_physicist.ltx"):
        wr_game(os.path.join(T, f), trade_file(os.path.join(T, f), norm, note="общие цены."))


# ---------------------------------------------------------------------------------------------
# 7. Списки для чтения: "Диалоги.txt" и "Описания.txt" в корне мода (собираются из готовых файлов)
# ---------------------------------------------------------------------------------------------
MOD_TEXTS = ("st_zz_diary.xml", "st_diary_pda.xml", "st_diary_pda_ui.xml")


def game_strings():
    """Все тексты (оригинал, затем мод) и id текстов мода."""
    allst, mod = {}, set()
    pat = r'<string id="([^"]+)">\s*<text>(.*?)</text>'
    for base_dir in (UE, PATCH):
        d = os.path.join(base_dir, "configs", "text", "rus")
        if os.path.isdir(d):
            for f in sorted(os.listdir(d)):
                with open(os.path.join(d, f), encoding=ENC, errors="replace") as fh:
                    allst.update(re.findall(pat, fh.read(), re.S))
    d = os.path.join(GAME, "configs", "text", "rus")
    for f in sorted(os.listdir(d)):
        pairs = re.findall(pat, rd(os.path.join(d, f)), re.S)
        allst.update(pairs)
        if f in MOD_TEXTS:
            mod |= {k for k, v in pairs}
    return allst, mod


def plain(s):
    return re.sub(r"\s+", " ", s.replace("\\n", " ")).strip()


SECTION_ORDER = ["Борода", "Сыч", "Тремор", "Кардан", "Султан", "Крим", "Гаваец", "Учёные"]
SECTION_OF = {"diary_zat_barmen": "Борода", "diary_zat_medic": "Тремор", "diary_zat_mechanic": "Кардан",
              "diary_zat_trader": "Сыч", "diary_krim": "Крим", "diary_sultan": "Султан", "diary_sci": "Учёные"}


def write_dialogs(allst):
    groups = {}
    tr = lambda sid: plain(allst.get(sid, sid))
    # кто ведёт диалог: персонажи с этим actor_dialog
    who = {}
    for f in ("character_desc_zaton.xml", "character_desc_jupiter.xml", "character_desc_general.xml"):
        p = os.path.join(GAME, "configs", "gameplay", f)
        if not os.path.exists(p):
            continue
        for m in re.finditer(r"<specific_character id=\"[^\"]+\".*?</specific_character>", rd(p), re.S):
            name = re.search(r"<name>(.*?)</name>", m.group(0))
            name = tr(name.group(1).strip()) if name else "?"
            for d in re.findall(r"<actor_dialog>(.*?)</actor_dialog>", m.group(0)):
                who.setdefault(d.strip(), [])
                if name not in who[d.strip()]:
                    who[d.strip()].append(name)
    for d in re.findall(r"<actor_dialog>(.*?)</actor_dialog>", rd(os.path.join(GAME, "configs", "gameplay", "character_dialogs.xml"))):
        who.setdefault(d.strip(), []).append("любой сталкер")
    out = ["Дневник проводника: все диалоги мода. Файл пишет сборщик (_src\\tools\\diary_build.py) -",
           "правки сюда не переносятся: тексты - _src\\configs\\text\\rus\\st_zz_diary.xml, диалоги -",
           "_src\\gen\\diary_dialogs.xml, задания - _src\\configs\\misc\\diary_jobs.ltx.",
           "Лазарь - реплики игрока; > - ответ собеседника; [!] - реплика видна не всегда (есть условие).", ""]
    who_names = {k: v[0] for k, v in speakers().items()}
    dz = rd(os.path.join(GAME, "configs", "gameplay", "dialogs_zaton.xml"))
    for m in re.finditer(r'<dialog id="((?:diary|dj)_[^"]+)"[^>]*>(.*?)</dialog>', dz, re.S):
        did, body = m.group(1), m.group(2)
        ph = {}
        for p in re.finditer(r'<phrase id="([^"]+)">(.*?)</phrase>', body, re.S):
            t = re.search(r"<text>(.*?)</text>", p.group(2))
            ph[p.group(1)] = (t.group(1).strip() if t else "", re.findall(r"<next>(.*?)</next>", p.group(2)),
                              "<precondition>" in p.group(2))
        main_out = out
        out = []
        out.append("=" * 100)
        out.append("%s  (%s)" % (did, ", ".join(who.get(did, ["-"]))))
        seen = set()

        def show(pid, depth):
            if pid not in ph:
                return
            text, nexts, cond = ph[pid]
            pad = "    " * depth
            speaker = "Лазарь: " if depth % 2 == 0 else "> "
            says = SPEECH.get(did + "|" + pid)
            if says:
                line = " / ".join("%s: %s" % (tr(who_names.get(w, w)), tr(s)) for w, s in says)
            else:
                line = tr(text) if text else "(без слов)"
            if pid in seen:
                out.append(pad + "... (к реплике: %s)" % line[:60])
                return
            seen.add(pid)
            if says:
                for k, (w, s) in enumerate(says):
                    out.append(pad + ("[!] " if cond and k == 0 else "") + "> %s: %s" % (tr(who_names.get(w, w)), tr(s)))
            else:
                out.append(pad + ("[!] " if cond else "") + speaker + line)
            for n in nexts:
                show(n, depth + 1)
        show("0", 0)
        out.append("")
        sec = SECTION_OF.get(did.split("_start")[0] if did.endswith("_start") or "_start_" in did else "", None)
        names = who.get(did, [])
        if sec is None:
            sec = names[0] if names else "Прочее"
            if sec not in SECTION_ORDER:
                sec = "Персонажи заданий" if sec != "любой сталкер" else "Любой сталкер"
        groups.setdefault(sec, []).append(out)
        out = main_out
    for sec in SECTION_ORDER + ["Персонажи заданий", "Любой сталкер", "Прочее"]:
        if sec not in groups:
            continue
        out.append("#" * 100)
        out.append("#  РАЗДЕЛ: %s  (диалогов: %d)" % (sec, len(groups[sec])))
        out.append("#" * 100)
        out.append("")
        for blk in groups[sec]:
            out.extend(blk)
    with open(os.path.join(ROOT, "Диалоги.txt"), "w", encoding="utf-8-sig", newline="\r\n") as f:
        f.write("\n".join(out))


DESC_GROUPS = [
    ("Задания: Лазарь", r"^diary_q\d+"),
    ("Задания линий", r"^dj_[a-z]\d+_(name|text|upd|done)"),
    ("Задания линий: общее", r"^dj_upd"),
    ("Предметы", r"^(dj_item_|diary_item|diary_.*outfit|diary_.*coat|st_|jup_|zat_)"),
    ("Люди", r"(_bio|_name)$"),
    ("Записи блокнота Лазаря", r"^diary_rec_"),
    ("КПК-блокнот", r"^diary_(pda|nbui|nb_)"),
    ("Блокнот Компаса и документы", r"^diary_(doc|dt|dl|reader|cipher)"),
    ("Сообщения", r"^diary_(news|mood|calm|rumor)"),
]


def write_descriptions(allst, mod):
    dz = rd(os.path.join(GAME, "configs", "gameplay", "dialogs_zaton.xml"))
    in_dialogs = set(re.findall(r"<text>([^<]+)</text>", dz))
    groups = {g: [] for g, _ in DESC_GROUPS}
    groups["Прочее"] = []
    for sid in sorted(mod - in_dialogs):
        g = next((g for g, rx in DESC_GROUPS if re.search(rx, sid)), "Прочее")
        groups[g].append(sid)
    out = ["Дневник проводника: все тексты мода, кроме реплик диалогов (они - в Диалоги.txt).",
           "Файл пишет сборщик. Править тексты: _src\\configs\\text\\rus\\st_zz_diary.xml (КПК - st_diary_pda*.xml).",
           "Слева id текста, справа сам текст.", ""]
    for g, ids in groups.items():
        if not ids:
            continue
        out.append("=" * 100)
        out.append("%s (%d)" % (g, len(ids)))
        out.append("=" * 100)
        for sid in ids:
            out.append("%-28s %s" % (sid, plain(allst.get(sid, ""))))
        out.append("")
    with open(os.path.join(ROOT, "Описания.txt"), "w", encoding="utf-8-sig", newline="\r\n") as f:
        f.write("\n".join(out))


def write_readable():
    allst, mod = game_strings()
    write_dialogs(allst)
    write_descriptions(allst, mod)


# ---------------------------------------------------------------------------------------------
# 8. Проверки
# ---------------------------------------------------------------------------------------------
def check():
    """Все id текстов из диалогов есть в строках; все функции dialogs_diary.* объявлены."""
    strings = set()
    for dp, dn, fn in os.walk(os.path.join(GAME, "configs", "text", "rus")):
        for f in fn:
            strings |= set(re.findall(r'<string id="([^"]+)"', rd(os.path.join(dp, f))))
    try:
        for f in os.listdir(os.path.join(UE, "configs", "text", "rus")):
            with open(os.path.join(UE, "configs", "text", "rus", f), encoding=ENC, errors="replace") as fh:
                strings |= set(re.findall(r'<string id="([^"]+)"', fh.read()))
    except Exception:
        pass
    dz = rd(os.path.join(GAME, "configs", "gameplay", "dialogs_zaton.xml"))
    texts = set(re.findall(r"<text>([a-z][a-z0-9_]+)</text>", dz))
    texts |= {s for says in SPEECH.values() for w, s in says}
    miss_t = sorted(t for t in texts if t not in strings and (t.startswith("dj_") or t.startswith("diary_")))
    dd = rd(os.path.join(GAME, "scripts", "dialogs_diary.script"))
    funcs = set(re.findall(r"dialogs_diary\.([a-z0-9_]+)", dz))
    declared = set(re.findall(r"(?m)^function ([a-z0-9_]+)\(", dd))
    generated = re.compile(r"^(o|a|r|d|c|l|p|dlv|dlv_here)_[a-z]\d+(_\d+)?$")
    miss_f = sorted(f for f in funcs if f not in declared and not generated.match(f)
                    and not re.match(r"^n6_m\d+$", f) and not re.match(r"^[cs]_(fresh|rest_open|can_full|can_half|can_rest|has_item|pay_full|pay_half|pay_rest|pay_item|steal)$", f))
    # у каждого character_profile в секциях мода есть <character id> в npc_profile.xml
    prof = set(re.findall(r'<character id="([^"]+)"', rd(os.path.join(GAME, "configs", "gameplay", "npc_profile.xml"))))
    for dp, dn, fn in os.walk(os.path.join(GAME, "configs")):
        for f in fn:
            if f.endswith(".ltx"):
                for m in re.findall(r"(?m)^\s*character_profile\s*=\s*(\w+)", rd(os.path.join(dp, f))):
                    if m not in prof:
                        miss_f.append("профиль %s (%s) - нет в npc_profile.xml" % (m, f))
    # у персонажа мода без своего приветствия группировка должна быть в общем hello_dialog
    # (иначе разговор - вылет "No available phrase to say, dialog[hello_dialog]")
    dm = ue(os.path.join("configs", "misc", "dialog_manager.ltx"))
    hello = set()
    for m in re.finditer(r"\[(dm_hello\w*)\]([^\[]*)", dm):
        c = re.search(r"npc_community\s*=\s*([^\n;]+)", m.group(2))
        hello |= {x.strip() for x in c.group(1).split(",")} if c else set()
    for f in ("character_desc_zaton.xml", "character_desc_jupiter.xml"):
        for m in re.finditer(r'<specific_character id="(diary_[^"]+)".*?</specific_character>',
                             rd(os.path.join(GAME, "configs", "gameplay", f)), re.S):
            comm = re.search(r"<community>\s*(\w+)", m.group(0))
            if comm and "<start_dialog>" not in m.group(0) and comm.group(1) not in hello:
                miss_f.append("приветствие %s (%s) - нет start_dialog, а у группировки нет фраз в hello_dialog"
                              % (m.group(1), comm.group(1)))
    # записи блокнота: у каждой diary_news.record("x") есть заголовок и текст
    for f in os.listdir(os.path.join(GAME, "scripts")):
        if f.endswith(".script"):
            for key in re.findall(r'diary_news\.record\("([a-z0-9_]+)"\)', rd(os.path.join(GAME, "scripts", f))):
                for suf in ("_t", "_x"):
                    if "diary_rec_" + key + suf not in strings:
                        miss_t.append("diary_rec_" + key + suf)
    return miss_t, miss_f


def lua_check():
    """Строгий синтаксис Lua 5.1 (luaparse через Node.js). Без Node проверка пропускается."""
    js = os.path.join(HERE, "lua_check", "check.js")
    try:
        r = subprocess.run(["node", js, os.path.join(GAME, "scripts")], capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
    except FileNotFoundError:
        print("! Node.js не найден - синтаксис Lua не проверен")
        return True
    if r.returncode != 0:
        print("! ОШИБКИ СИНТАКСИСА LUA (скрипт не загрузится в игре):")
        print(r.stdout.strip())
        return False
    return True


def remove_stale():
    """В gamedata остаётся только собранное: прочее (старые версии мода) переносится в
    _backup\\removed_from_gamedata - не удаляется насовсем."""
    keep = {os.path.normcase(os.path.normpath(r)) for r in written}
    if not DEV:
        keep |= {os.path.normcase(os.path.normpath(r)) for r in walk("dev")}
    moved = []
    for top in ("configs", "scripts", "textures", "spawns"):
        for dp, dn, fn in os.walk(os.path.join(GAME, top)):
            for f in fn:
                rel = os.path.relpath(os.path.join(dp, f), GAME)
                if os.path.normcase(rel) not in keep:
                    dst = os.path.join(ROOT, "_backup", "removed_from_gamedata", rel)
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    shutil.move(os.path.join(GAME, rel), dst)
                    moved.append(rel)
    return moved


def main():
    order, jobs = read_jobs()
    copy_sources()
    hub_attach, jattach, extra_attach = build_dialogs(order, jobs)
    missing_chars = build_characters(hub_attach, jattach, extra_attach)
    build_tasks(order, jobs)
    build_ui()
    build_actor()
    build_items()
    build_trade()
    stale = remove_stale()
    miss_t, miss_f = check()
    lua_ok = lua_check()
    write_readable()
    print("Собрано файлов: %d (%s)" % (len(written), "сборка разработчика" if DEV else "релиз"))
    if lua_ok:
        print("Синтаксис Lua: без ошибок")
    if stale:
        print("Убрано из gamedata (нет в _src, перенесено в _backup\\removed_from_gamedata):", len(stale))
        for rel in stale:
            print("   ", rel)
    if missing_chars:
        print("! Нет персонажей для тем:", ", ".join(missing_chars))
    if miss_t:
        print("! Нет строк:", ", ".join(miss_t))
    if miss_f:
        print("! Нет функций в dialogs_diary.script:", ", ".join(miss_f))


if __name__ == "__main__":
    main()
