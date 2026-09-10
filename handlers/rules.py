# -*- coding: utf-8 -*-
"""Rules and documentation handler: /rules_map command."""

import io
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.colors import HexColor, white
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak,
    Table, TableStyle, KeepTogether,
)
from reportlab.platypus.flowables import Flowable
from aiogram import F, Router
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import Message, BufferedInputFile
from internationalization import _
from tg.helpers import send_message
from ui.text_style import menu_title_bar, menu_heading_bold, smallcaps

router = Router(name="rules")

# ── Palette ─────────────────────────────────────────────────────
MC = {
    "CL": HexColor("#2563EB"),
    "FS": HexColor("#16A34A"),
    "WD": HexColor("#7C3AED"),
    "RB": HexColor("#EA580C"),
    "TX": HexColor("#0891B2"),
    "SD": HexColor("#DC2626"),
    "BL": HexColor("#B45309"),
    "PV": HexColor("#0F766E"),
    "TM": HexColor("#059669"),
}
C_DARK   = HexColor("#0F172A")
C_MID    = HexColor("#334155")
C_LIGHT  = HexColor("#F1F5F9")
C_BORDER = HexColor("#CBD5E1")
C_GOLD   = HexColor("#F59E0B")
C_SUBTLE = HexColor("#64748B")
C_WHITE  = white

MARGIN = 13 * mm


# ── Helpers ──────────────────────────────────────────────────────
def sp(n=4):
    return Spacer(1, n)

def _p(text, fs=8, bold=False, color=None, align=TA_LEFT, leading=None):
    """Quick Paragraph factory — always wraps, never overflows."""
    fn = "Helvetica-Bold" if bold else "Helvetica"
    lh = leading or (fs * 1.4)
    return Paragraph(text, ParagraphStyle(
        "_p", fontName=fn, fontSize=fs, leading=lh,
        textColor=color or C_MID, alignment=align,
        spaceAfter=0, spaceBefore=0,
    ))

def _ph(text, fs=8, bold=False, color=None, align=TA_LEFT):
    """Paragraph for table header row (white text, bold)."""
    return _p(text, fs=fs, bold=True, color=color or C_WHITE, align=align)


# ── Custom flowable: ModeBadge ───────────────────────────────────
class ModeBadge(Flowable):
    """Coloured pill badge + title + coloured underline."""
    H = 30

    def __init__(self, code, title, subtitle=""):
        super().__init__()
        self.code     = code
        self.title    = title
        self.subtitle = subtitle
        self.color    = MC.get(code, C_DARK)

    def wrap(self, availW, availH):
        self._w = availW
        return availW, self.H + 6

    def draw(self):
        c, col, h, w = self.canv, self.color, self.H, self._w
        bw = 38
        # pill
        c.setFillColor(col)
        c.roundRect(0, 4, bw, h - 8, 6, fill=1, stroke=0)
        c.setFillColor(C_WHITE)
        c.setFont("Helvetica-Bold", 10)
        c.drawCentredString(bw / 2, 4 + (h - 8) / 2 - 4, self.code)
        # title
        c.setFillColor(C_DARK)
        c.setFont("Helvetica-Bold", 13)
        c.drawString(bw + 9, h / 2, self.title)
        # subtitle
        if self.subtitle:
            c.setFillColor(C_SUBTLE)
            c.setFont("Helvetica", 8)
            c.drawString(bw + 9, h / 2 - 12, self.subtitle)
        # underline
        c.setStrokeColor(col)
        c.setLineWidth(1.8)
        c.line(0, 0, w, 0)


class ThinRule(Flowable):
    def __init__(self, color=C_BORDER, thick=0.5):
        super().__init__()
        self._color = color
        self._thick = thick

    def wrap(self, aw, ah):
        self._w = aw
        return aw, self._thick + 4

    def draw(self):
        self.canv.setStrokeColor(self._color)
        self.canv.setLineWidth(self._thick)
        self.canv.line(0, 2, self._w, 2)


# ── Page header / footer ─────────────────────────────────────────
def _on_page(canv, doc):
    canv.saveState()
    w, h = A4
    # header
    canv.setFillColor(C_DARK)
    canv.rect(0, h - 22, w, 22, fill=1, stroke=0)
    canv.setFillColor(C_GOLD)
    canv.setFont("Helvetica-Bold", 9)
    canv.drawString(MARGIN, h - 14, "UNO BOT")
    canv.setFillColor(C_WHITE)
    canv.setFont("Helvetica", 8)
    canv.drawString(MARGIN + 44, h - 14, "|  Complete Rules Guide")
    canv.drawRightString(w - MARGIN, h - 14, f"Page {doc.page}")
    # mode colour stripe under header
    codes = ["CL", "FS", "WD", "RB", "TX", "SD"]
    sw = w / len(codes)
    for i, code in enumerate(codes):
        canv.setFillColor(MC[code])
        canv.rect(i * sw, h - 25, sw, 3, fill=1, stroke=0)
    # footer
    canv.setFillColor(C_DARK)
    canv.rect(0, 0, w, 15, fill=1, stroke=0)
    canv.setFillColor(HexColor("#94A3B8"))
    canv.setFont("Helvetica", 7)
    canv.drawCentredString(w / 2, 4,
        "(c) 2026 UNO Telegram Bot  |  @demon_botzz  |  Bot: @demon12809")
    canv.restoreState()


# ── Table builder helper ─────────────────────────────────────────
def _mode_table(doc, rows, code):
    """
    rows = list of (label_str, [line_str, ...]) tuples.
    Label column is narrow; content column wraps properly.
    """
    col = MC[code]
    LW  = 24 * mm
    CW  = doc.width - LW

    data = []
    for label, lines in rows:
        content = _p("<br/>".join(lines), fs=8, color=C_MID)
        data.append([
            _p(label, fs=8, bold=True, color=col),
            content,
        ])

    t = Table(data, colWidths=[LW, CW], repeatRows=0)
    t.setStyle(TableStyle([
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [C_LIGHT, C_WHITE]),
        ("TOPPADDING",     (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING",  (0, 0), (-1, -1), 5),
        ("LEFTPADDING",    (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",   (0, 0), (-1, -1), 6),
        ("GRID",           (0, 0), (-1, -1), 0.35, C_BORDER),
        ("VALIGN",         (0, 0), (-1, -1), "TOP"),
    ]))
    return t


# ── PDF generator ────────────────────────────────────────────────
def _generate_rules_pdf() -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=MARGIN + 25,   # space for header + stripe
        bottomMargin=MARGIN + 15,
        title="UNO Bot Complete Rules Guide",
    )
    story = []

    # ════════════════════════════════════════════════════════════
    # PAGE 1  –  Classic · Fast · Wild · Rainbow
    # ════════════════════════════════════════════════════════════

    # ── Classic ─────────────────────────────────────────────────
    story.append(ModeBadge("CL", "Classic Mode",
                            "Traditional 108-card UNO"))
    story.append(sp(5))
    story.append(_mode_table(doc, [
        ("Deck",    ["108 cards  |  4 colours: Red, Blue, Green, Yellow",
                     "Numbers 0-9 (one 0, two each of 1-9 per colour)",
                     "Skip / Reverse / +2 — 2 cards each per colour  |  4 Wild  |  4 Wild +4"]),
        ("Start",   ["7 cards per player"]),
        ("Play",    ["Match the top card by colour, number, or symbol.",
                     "No match? Draw 1 card. If it plays, use it immediately."]),
        ("Win",     ["First to empty hand wins. Bot auto-calls UNO at 1 card left."]),
        ("Special", ["Skip [/]  — next player loses turn",
                     "Reverse [<>]  — flip play direction",
                     "+2  — next player draws 2 and loses turn",
                     "Wild [W]  — freely choose any colour",
                     "Wild +4  — choose colour; next draws 4 and loses turn"]),
        ("Bluff",   ["Wild +4 is only legal when you hold NO card matching the current colour.",
                     "Next player may challenge. If bluff confirmed: bluffer draws 4.",
                     "If challenge is wrong: challenger draws 6."]),
    ], "CL"))
    story.append(sp(10))

    # ── Fast ────────────────────────────────────────────────────
    story.append(ModeBadge("FS", "Fast Mode  (Sanic)",
                            "Classic + countdown auto-skip timer"))
    story.append(sp(5))
    story.append(_mode_table(doc, [
        ("Timer",    ["30 s turn grace  |  −5 s per penalty skip  |  15 s Fast auto-skip floor"]),
        ("Mechanic", ["Fast: countdown ends → auto-skip; forced skips cut grace by 5 s while it lasts.",
                      "Classic & other modes: same grace gates /skip — no auto countdown."]),
        ("Bluff",    ["Bluffing and challenges fully active — same rules as Classic."]),
        ("Other",    ["Identical to Classic in all other respects."]),
    ], "FS"))
    story.append(sp(10))

    # ── Wild ────────────────────────────────────────────────────
    story.append(ModeBadge("WD", "Wild Mode",
                            "Chaos — extra action cards, fewer numbers"))
    story.append(sp(5))
    story.append(_mode_table(doc, [
        ("Deck",    ["6 copies of each action card per colour (vs 2 in Classic).",
                     "More Wild +4. Fewer number cards overall."]),
        ("Effect",  ["Action cards appear far more often — expect rapid colour changes,",
                     "direction flips, and draw-card chains every few turns."]),
        ("Bluff",   ["Bluffing and challenges active — same rules as Classic."]),
        ("Other",   ["Otherwise identical to Classic."]),
    ], "WD"))
    story.append(sp(10))

    # ── Rainbow ─────────────────────────────────────────────────
    story.append(ModeBadge("RB", "Rainbow Mode",
                            "6 colours  |  162-card deck  |  Power cards"))
    story.append(sp(5))
    story.append(_mode_table(doc, [
        ("Deck",    ["162 cards  |  6 colours: Red, Blue, Green, Yellow, Purple, Orange",
                     "6-card starting hand  |  All Classic card types present for each colour"]),
        ("Power",   ["Rainbow +8  — next player draws 8 cards",
                     "Rainbow Wild  — play on any card, choose any colour freely",
                     "Rainbow Monster  — ALL other players each draw 2 cards",
                     "Rainbow Lightning  — reverses direction AND skips next player"]),
        ("Bluff",   ["Bluffing and challenges are active in Rainbow mode.",
                     "Wild +4 challenge rules apply as in Classic."]),
        ("Note",    ["Power cards (+8, Monster, Lightning) cannot be challenged.",
                     "Only the standard Wild +4 bluff challenge applies."]),
    ], "RB"))

    story.append(sp(8))

    # ── Text ────────────────────────────────────────────────────
    story.append(ModeBadge("TX", "Text Mode",
                            "Classic rules — text display instead of sticker cards"))
    story.append(sp(5))
    story.append(_mode_table(doc, [
        ("Display", ["Cards shown as plain text: 'Red 7', 'Blue Skip', 'Wild +4', etc.",
                     "No image stickers — full text-only interface."]),
        ("Purpose", ["Accessibility & screen reader compatibility  |  Low-bandwidth play"]),
        ("Bluff",   ["Bluffing and challenges active — same rules as Classic."]),
        ("Other",   ["Identical to Classic in every other respect."]),
    ], "TX"))
    story.append(sp(10))

    # ── Sudden Death ────────────────────────────────────────────
    story.append(ModeBadge("SD", "Sudden Death Mode",
                            "Classic rules — game ends the instant the first player wins"))
    story.append(sp(5))
    story.append(_mode_table(doc, [
        ("Deck",    ["Standard Classic 108-card deck  |  7 cards starting hand"]),
        ("Rule",    ["Game ends IMMEDIATELY when first player empties their hand.",
                     "No 2nd or 3rd place — one winner, game over."]),
        ("Points",  ["Winner: 180 pts  |  Participants: 15 pts  |  No placement bonuses.",
                     "High winner bonus rewards decisive, aggressive play."]),
        ("Bluff",   ["Bluffing and challenges active — same rules as Classic."]),
    ], "SD"))
    story.append(sp(12))

    # ── Points Comparison ────────────────────────────────────
    story.append(ThinRule(C_GOLD, thick=1.5))
    story.append(sp(7))
    story.append(Paragraph("Points Comparison — All Modes", ParagraphStyle(
        "_sec", fontName="Helvetica-Bold", fontSize=10,
        textColor=C_DARK, spaceAfter=5,
    )))
    story.append(sp(5))

    modes_pts = [
        ("CL", "Classic",      "120", "80", "40", "25"),
        ("FS", "Fast",         "120", "80", "40", "25"),
        ("WD", "Wild",         "120", "80", "40", "25"),
        ("RB", "Rainbow",      "120", "80", "40", "25"),
        ("TX", "Text",         "120", "80", "40", "25"),
        ("SD", "Sudden Death", "180", "--", "--", "15"),
        ("TM", "Team",         "80",  "20", "10", "25"),
    ]
    hdr_style = ParagraphStyle("_h", fontName="Helvetica-Bold", fontSize=8,
                               textColor=C_WHITE, alignment=TA_CENTER)
    cell_style = ParagraphStyle("_c", fontName="Helvetica", fontSize=8,
                                textColor=C_MID, alignment=TA_CENTER)
    bold_cell  = ParagraphStyle("_cb", fontName="Helvetica-Bold", fontSize=8,
                                textColor=C_MID, alignment=TA_CENTER)

    cws = [doc.width * r for r in [0.24, 0.19, 0.19, 0.19, 0.19]]
    pt_data = [[
        Paragraph("Mode",        hdr_style),
        Paragraph("Winner",      hdr_style),
        Paragraph("2nd Place",   hdr_style),
        Paragraph("3rd Place",   hdr_style),
        Paragraph("Participant", hdr_style),
    ]]
    for code, name, w1, w2, w3, wp in modes_pts:
        name_p = Paragraph(name, ParagraphStyle(
            "_nm", fontName="Helvetica-Bold", fontSize=8,
            textColor=C_WHITE, alignment=TA_CENTER,
        ))
        pt_data.append([name_p,
                        Paragraph(w1, bold_cell if code == "SD" else cell_style),
                        Paragraph(w2, cell_style),
                        Paragraph(w3, cell_style),
                        Paragraph(wp, bold_cell if code == "SD" else cell_style)])

    pt = Table(pt_data, colWidths=cws)
    ts = TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0),  C_DARK),
        ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 4),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 4),
        ("GRID",          (0, 0), (-1, -1), 0.4, C_BORDER),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [C_LIGHT, C_WHITE]),
        # Sudden Death row highlight
        ("BACKGROUND",    (0, 6), (-1, 6),  HexColor("#FEE2E2")),
        ("FONTNAME",      (0, 6), (-1, 6),  "Helvetica-Bold"),
    ])
    # colour the mode name column per mode
    for i, (code, *_) in enumerate(modes_pts, start=1):
        ts.add("BACKGROUND", (0, i), (0, i), MC[code])
    pt.setStyle(ts)
    story.append(pt)

    story.append(PageBreak())

    # ════════════════════════════════════════════════════════════
    # PAGE 3  –  Bluff Rules · Private Mode · Group Commands
    # ════════════════════════════════════════════════════════════

    # ── Bluff Rules ─────────────────────────────────────────────
    story.append(ModeBadge("BL", "Bluff Rules",
                            "Challenge Wild +4 plays across all modes"))
    story.append(sp(5))
    story.append(_mode_table(doc, [
        ("What",      ["Playing Wild +4 (or Rainbow +8) when you COULD play a regular card.",
                       "Bluffing is high-risk, high-reward — use it wisely."]),
        ("Modes",     ["Bluffing ALLOWED in: Classic, Fast, Wild, Rainbow, Text, Sudden Death.",
                       "No mode disables bluffing — it is active everywhere."]),
        ("Challenge", ["Only the player who just drew the penalty cards may challenge.",
                       "Bluff CONFIRMED → bluffer draws 4 penalty cards.",
                       "Bluff FALSE (wrong challenge) → challenger draws 6 cards.",
                       "Challenge must be made immediately after drawing — no delay."]),
        ("Legal play",["Wild +4 is legal ONLY when you hold no card matching the current colour.",
                       "Matching means same colour. Number or symbol alone does not qualify.",
                       "Standard Wild cards (no draw) are always legal to play."]),
        ("Note",      ["Rainbow Power cards (+8, Monster, Lightning) cannot be challenged.",
                       "Only the Wild +4 bluff challenge mechanic applies to those."]),
    ], "BL"))
    story.append(sp(10))

    # ── Private Mode ────────────────────────────────────────────
    story.append(ModeBadge("PV", "Private Mode",
                            "Invite-only games via join code"))
    story.append(sp(5))
    story.append(_mode_table(doc, [
        ("Create",  ["/privatenew in bot DM  →  choose mode  →  receive a join code"]),
        ("Join",    ["/joincode <code> in bot DM  →  bot adds you to the lobby"]),
        ("Manage",  ["/kick @user — remove a player before game starts",
                     "/leave — exit lobby at any time  |  min 2 players to start",
                     "/cancelprivate — dissolve the entire lobby (host only)"]),
        ("Start",   ["Host sends /start_match — cards are dealt privately to each player's DM.",
                     "All 6 game modes are available in private sessions."]),
    ], "PV"))
    story.append(sp(12))

    # ── Group Commands ──────────────────────────────────────────
    story.append(ThinRule(C_BORDER))
    story.append(sp(7))
    story.append(Paragraph("Group Game Commands", ParagraphStyle(
        "_gc", fontName="Helvetica-Bold", fontSize=10,
        textColor=C_DARK, spaceAfter=5,
    )))
    story.append(sp(5))

    cmd_rows = [
        ("/new",       "Create a new game lobby in the group"),
        ("/join",      "Join the current open lobby"),
        ("/start",     "Start the game  (creator / admin only)"),
        ("/leave",     "Leave the lobby or an active game"),
        ("/kill",      "Force-end the game  (admin only)"),
        ("@unor0bot",  "Open your inline card picker to play a card"),
        ("/rules_map", "Download this rules PDF"),
        ("/stats",     "View your personal win / loss statistics"),
        ("/help",      "Show the full command reference"),
    ]
    cmd_data = [[
        _p(cmd, fs=8, bold=True, color=C_DARK),
        _p(desc, fs=8, color=C_MID),
    ] for cmd, desc in cmd_rows]

    cmd_cw = [38 * mm, doc.width - 38 * mm]
    cmdt = Table(cmd_data, colWidths=cmd_cw)
    cmdt.setStyle(TableStyle([
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [C_LIGHT, C_WHITE]),
        ("TOPPADDING",     (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING",  (0, 0), (-1, -1), 4),
        ("LEFTPADDING",    (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",   (0, 0), (-1, -1), 6),
        ("GRID",           (0, 0), (-1, -1), 0.35, C_BORDER),
        ("VALIGN",         (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(cmdt)
    story.append(sp(12))

    # ── Bluff Penalty Quick-Reference Box ───────────────────────
    story.append(ThinRule(C_GOLD, thick=1.5))
    story.append(sp(7))
    story.append(Paragraph("Bluff Penalty Quick Reference", ParagraphStyle(
        "_bp", fontName="Helvetica-Bold", fontSize=10,
        textColor=C_DARK, spaceAfter=5,
    )))
    story.append(sp(5))

    bluff_rows = [
        ("Bluff CONFIRMED — caught bluffing",  "Bluffer draws 4 cards"),
        ("Bluff FALSE — wrong challenge",       "Challenger draws 6 cards"),
        ("Challenge window",                    "Immediately after drawing penalty cards only"),
        ("Power cards (+8 / Monster / Lightning)", "Cannot be challenged — no bluff applies"),
    ]
    bl_data = [[
        _p(left, fs=8, bold=True, color=C_MID),
        _p(right, fs=8, color=C_MID),
    ] for left, right in bluff_rows]

    blt = Table(bl_data, colWidths=[doc.width * 0.54, doc.width * 0.46])
    blt.setStyle(TableStyle([
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [HexColor("#FFFBEA"), C_WHITE]),
        ("TOPPADDING",     (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING",  (0, 0), (-1, -1), 5),
        ("LEFTPADDING",    (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",   (0, 0), (-1, -1), 6),
        ("GRID",           (0, 0), (-1, -1), 0.35, C_BORDER),
        ("VALIGN",         (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(blt)
    story.append(sp(10))

    # ── Team Mode ───────────────────────────────────────
    story.append(ModeBadge("TM", "Team Mode",
                            "2v2 / 3v3 competitive team play"))
    story.append(sp(5))
    story.append(_mode_table(doc, [
        ("Create",  ["/teamnew in group → choose 2v2 or 3v3 → manual team assignment",
                     "or 2v2 Random / 3v3 Random → automatic balanced teams"]),
        ("Setup",   ["Team size: 2-6 players per team",
                     "Team names customizable (Team A, Team B)",
                     "Shared team hands visible to all team members"]),
        ("Play",    ["Turn order alternates between teams",
                     "Team members can see each other's cards",
                     "Individual turns but team victory"]),
        ("Win",     ["First team to have all members empty their hands wins",
                     "Team victory shared among all team members",
                     "Individual stats still tracked"]),
        ("Strategy", ["Team coordination required for optimal play",
                     "Communication between team members essential",
                     "Balance risk across team members"]),
    ], "TM"))
    story.append(sp(12))

    # ── Special Cards Cheat-Sheet ───────────────────────────────
    story.append(ThinRule(C_BORDER))
    story.append(sp(7))
    story.append(Paragraph("Special Cards Cheat-Sheet", ParagraphStyle(
        "_cs", fontName="Helvetica-Bold", fontSize=10,
        textColor=C_DARK, spaceAfter=5,
    )))
    story.append(sp(5))

    cheat_rows = [
        ("Skip [/]",             "Next player in turn order loses their turn"),
        ("Reverse [<>]",         "Flips the direction of play"),
        ("+2",                   "Next player draws 2 cards and loses their turn"),
        ("Wild [W]",             "Freely change the active colour"),
        ("Wild +4",              "Choose colour; next player draws 4 and loses turn. Can be challenged."),
        ("Rainbow +8",           "Next player draws 8 cards  (Rainbow mode only)"),
        ("Rainbow Wild",         "Play on any card and choose any colour  (Rainbow mode only)"),
        ("Rainbow Monster",      "ALL other players each draw 2 cards  (Rainbow mode only)"),
        ("Rainbow Lightning",    "Reverses direction AND skips the next player  (Rainbow mode only)"),
    ]
    cs_data = [[
        _p(card, fs=8, bold=True, color=C_DARK),
        _p(effect, fs=8, color=C_MID),
    ] for card, effect in cheat_rows]

    cst = Table(cs_data, colWidths=[50 * mm, doc.width - 50 * mm])
    cst.setStyle(TableStyle([
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [C_LIGHT, C_WHITE]),
        ("TOPPADDING",     (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING",  (0, 0), (-1, -1), 4),
        ("LEFTPADDING",    (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",   (0, 0), (-1, -1), 6),
        ("GRID",           (0, 0), (-1, -1), 0.35, C_BORDER),
        ("VALIGN",         (0, 0), (-1, -1), "MIDDLE"),
        # Rainbow rows — light orange tint
        ("BACKGROUND",     (0, 5), (-1, 8),  HexColor("#FFF7ED")),
    ]))
    story.append(cst)
    story.append(sp(12))

    # ── Credits ────────────────────────────────────────
    qr_modes = [
        ("CL", "Classic",       "108 / 4 col", "7", "No",  "Yes", "Standard play"),
        ("FS", "Fast",          "108 / 4 col", "7", "30s","Yes", "Auto-skip timer"),
        ("WD", "Wild",          "Larger / 4",  "7", "No",  "Yes", "6x action cards"),
        ("RB", "Rainbow",       "162 / 6 col", "6", "No",  "Yes", "+8 / Monster / Lightning"),
        ("TX", "Text",         "108 / 4 col", "7", "No",  "Yes", "Text display only"),
        ("SD", "Sudden Death",  "108 / 4 col", "7", "No",  "Yes", "1st winner ends game"),
        ("TM", "Team",         "Same as mode", "Variable", "No",  "Yes", "2v2 / 3v3 competition"),
    ]
    qr_cws = [
        doc.width * 0.13, doc.width * 0.17,
        doc.width * 0.17, doc.width * 0.08,
        doc.width * 0.10, doc.width * 0.10,
        doc.width * 0.25,
    ]
    qr_hdr = ParagraphStyle("_h", fontName="Helvetica-Bold", fontSize=8,
                               textColor=C_WHITE, alignment=TA_CENTER)
    qr_bold = ParagraphStyle("_cb", fontName="Helvetica-Bold", fontSize=8,
                                textColor=C_MID, alignment=TA_CENTER)
    qr_cell = ParagraphStyle("_c", fontName="Helvetica", fontSize=8,
                                textColor=C_MID, alignment=TA_CENTER)
    qr_data = [[
        Paragraph("Code",    qr_hdr),
        Paragraph("Mode",    qr_hdr),
        Paragraph("Deck",    qr_hdr),
        Paragraph("Hand",    qr_hdr),
        Paragraph("Timer",   qr_hdr),
        Paragraph("Bluff",   qr_hdr),
        Paragraph("Special", qr_hdr),
    ]]
    for code, name, deck, hand, timer, bluff, special in qr_modes:
        badge_p = Paragraph(code, ParagraphStyle(
            "_badge", fontName="Helvetica-Bold", fontSize=7.5,
            textColor=C_WHITE, alignment=TA_CENTER,
        ))
        qr_data.append([
            badge_p,
            Paragraph(name,    qr_bold),
            Paragraph(deck,    qr_cell),
            Paragraph(hand,    qr_cell),
            Paragraph(timer,   qr_cell),
            Paragraph(bluff,   qr_cell),
            Paragraph(special, qr_cell),
        ])

    qrt = Table(qr_data, colWidths=qr_cws)
    qr_ts = TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0),  C_DARK),
        ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 3),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 3),
        ("GRID",          (0, 0), (-1, -1), 0.4, C_BORDER),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [C_LIGHT, C_WHITE]),
    ])
    for i, (code, *_) in enumerate(qr_modes, start=1):
        qr_ts.add("BACKGROUND", (0, i), (1, i), MC[code])
    qrt.setStyle(qr_ts)
    story.append(qrt)
    story.append(sp(8))

    # ── Credits ─────────────────────────────────────────────────
    story.append(ThinRule(C_GOLD, thick=1.5))
    story.append(sp(7))
    cred_data = [[
        _p("Bot Creator",  fs=8, bold=True, color=C_SUBTLE),
        _p("@demon12809",  fs=8, color=MC["CL"]),
        _p("Support Group",fs=8, bold=True, color=C_SUBTLE),
        _p("@demon_botzz", fs=8, color=MC["FS"]),
        _p("Version",      fs=8, bold=True, color=C_SUBTLE),
        _p("2.0 / 2026",   fs=8, color=C_MID),
    ]]
    cred = Table(cred_data, colWidths=[
        doc.width*0.13, doc.width*0.20,
        doc.width*0.16, doc.width*0.20,
        doc.width*0.11, doc.width*0.20,
    ])
    cred.setStyle(TableStyle([
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING",   (0, 0), (-1, -1), 4),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(cred)

    # ── Build ────────────────────────────────────────────────────
    doc.build(story, onFirstPage=_on_page, onLaterPages=_on_page)
    buf.seek(0)
    return buf.getvalue()


# ── Telegram handler ─────────────────────────────────────────────
@router.message(Command("rules_map"))
async def cmd_rules_map(message: Message, bot) -> None:
    caption = (
        f"<tg-emoji emoji-id=\"6314237464315696206\">✨</tg-emoji>""ᴄʜᴇᴄᴋᴏᴜᴛ ᴀʟʟ ᴍᴏᴅᴇ ʀᴜʟᴇꜱ & ꜱᴛʀᴜᴄᴛᴜʀᴇ ɪɴ ɢᴀᴍᴇ\n\n"
    )
    from ui.inline_buttons import btn_url, markup
    await send_message(
        bot, 
        message.chat.id, 
        caption, 
        parse_mode=ParseMode.HTML,
        reply_markup=markup([
            [btn_url("ᴄʟɪᴄᴋ ʜᴇʀᴇ", "https://telegra.ph/%F0%9D%90%94i%CF%83-%F0%9D%90%81%CF%83t-04-24", "danger", icon_role="rules_btn")]
        ])
    )