"""reminders.py - build polite payment-reminder text from a shop's real overdue invoices. No AI, nothing sent."""
import sqlite3
from copilot.store import create_draft, list_drafts
from copilot.finance import get_open_invoices

MAX_LISTED_INVOICES = 10     # list at most 10 invoices in one reminder; mention the rest as a count

# The tone paragraph depends on how late the oldest bill is.
TONE_TEXT = {
    "en": {
        "gentle": ("If you have already arranged payment, please ignore this message. Otherwise, we would be "
                   "grateful if you could settle the amount or contact your sales representative, {rep}, "
                   "to arrange payment."),
        "firm": ("We kindly ask you to settle the amount within 7 days, or contact your sales "
                 "representative, {rep}, to agree a payment date."),
        "final": ("Some of these invoices are now more than 90 days overdue. Please settle the amount within "
                  "7 days. New orders on credit may be put on hold until the account is up to date. "
                  "Your sales representative, {rep}, can help if you would like to discuss a payment plan."),
    },
    "ar": {
        "gentle": ("إذا كنتم قد قمتم بالدفع بالفعل، يرجى تجاهل هذه الرسالة. وإلا فنرجو التكرم بسداد المبلغ "
                   "أو التواصل مع مندوب المبيعات {rep} لترتيب الدفع."),
        "firm": "نرجو التكرم بسداد المبلغ خلال 7 أيام، أو التواصل مع مندوب المبيعات {rep} للاتفاق على موعد الدفع.",
        "final": ("بعض هذه الفواتير متأخرة لأكثر من 90 يومًا. نرجو سداد المبلغ خلال 7 أيام، وقد يتم إيقاف الطلبات "
                  "الآجلة الجديدة مؤقتًا إلى حين تسوية الحساب. يمكن لمندوب المبيعات {rep} مساعدتكم إذا رغبتم "
                  "في مناقشة خطة للدفع."),
    },
}


def get_customer_contact(con: sqlite3.Connection, customer_id: int) -> dict:
    """Name, contact person, email, phone, TRN, preferred language and main salesman of one shop."""
    row = con.execute("""
        SELECT c.id AS customer_id, c.name AS customer_name, c.contact_person, c.email, c.phone,
               p.trn, COALESCE(p.preferred_language, 'en') AS language, u.name AS rep_name
        FROM customers c
        LEFT JOIN ext_customer_profile p ON p.customer_id = c.id
        LEFT JOIN users u ON u.id = p.main_rep_id
        WHERE c.id = ?""", (customer_id,)).fetchone()
    if row is None:
        raise ValueError(f"Customer {customer_id} not found")
    return dict(row)


def get_overdue_invoices(con: sqlite3.Connection, customer_id: int, as_of: str) -> list[dict]:
    """One shop's unpaid bills that are past their due date, oldest first."""
    return [inv for inv in get_open_invoices(con, as_of)
            if inv["customer_id"] == customer_id and inv["days_overdue"] > 0]


def choose_channel(contact: dict) -> tuple[str, str] | None:
    """Email if the shop has one, otherwise SMS to its phone, otherwise None (no way to reach it)."""
    if contact.get("email"):
        return "email", contact["email"]
    if contact.get("phone"):
        return "sms", contact["phone"]
    return None


def tone_for(worst_days_overdue: int) -> str:
    """How firm the reminder should be, based on the oldest overdue bill."""
    if worst_days_overdue <= 30:
        return "gentle"
    if worst_days_overdue <= 90:
        return "firm"
    return "final"


def build_reminder(contact: dict, invoices: list[dict], language: str = "en", currency: str = "AED") -> dict:
    """Write the subject and body of a reminder in English ('en') or Arabic ('ar')."""
    if not invoices:
        raise ValueError(f"{contact['customer_name']} has no overdue invoices")
    total = round(sum(inv["balance"] for inv in invoices), 2)
    worst = max(inv["days_overdue"] for inv in invoices)
    rep = contact.get("rep_name") or ("our accounts team" if language == "en" else "قسم الحسابات")
    person = contact.get("contact_person") or contact["customer_name"]
    listed = invoices[:MAX_LISTED_INVOICES]
    more = len(invoices) - len(listed)

    if language == "en":
        lines = [f"  {inv['order_no']}  due {inv['due_date']}  {currency} {inv['balance']:,.2f}"
                 f"  ({inv['days_overdue']} days overdue)" for inv in listed]
        if more:
            lines.append(f"  ...and {more} more overdue invoice(s).")
        subject = f"Payment reminder: {len(invoices)} overdue invoice(s), {currency} {total:,.2f}"
        body = "\n".join([
            f"Dear {person},",
            "",
            f"This is a reminder that the following invoice(s) for {contact['customer_name']} "
            "are past their due date:",
            "",
            *lines,
            "",
            f"Total overdue: {currency} {total:,.2f}",
            *([f"Customer TRN: {contact['trn']}"] if contact.get("trn") else []),
            "",
            TONE_TEXT["en"][tone_for(worst)].format(rep=rep),
            "",
            "Kind regards,",
            "Accounts Team",
        ])
    elif language == "ar":
        lines = [f"  {inv['order_no']}  تاريخ الاستحقاق {inv['due_date']}  المبلغ {inv['balance']:,.2f} {currency}"
                 f"  (متأخرة {inv['days_overdue']} يومًا)" for inv in listed]
        if more:
            lines.append(f"  ...بالإضافة إلى {more} فاتورة متأخرة أخرى.")
        subject = f"تذكير بالدفع: {len(invoices)} فاتورة متأخرة، {total:,.2f} {currency}"
        body = "\n".join([
            f"السيد/السيدة {person} المحترم/ة،",
            "",
            "تحية طيبة وبعد،",
            f"نود تذكيركم بأن الفواتير التالية الخاصة بـ {contact['customer_name']} قد تجاوزت تاريخ استحقاقها:",
            "",
            *lines,
            "",
            f"إجمالي المبلغ المتأخر: {total:,.2f} {currency}",
            *([f"الرقم الضريبي للعميل: {contact['trn']}"] if contact.get("trn") else []),
            "",
            TONE_TEXT["ar"][tone_for(worst)].format(rep=rep),
            "",
            "مع خالص التحية،",
            "قسم الحسابات",
        ])
    else:
        raise ValueError(f"Unsupported language: {language}")

    return {"subject": subject, "body": body, "amount_due": total,
            "invoice_refs": [inv["order_no"] for inv in invoices], "tone": tone_for(worst)}

def draft_reminder(billing: sqlite3.Connection, store: sqlite3.Connection, customer_id: int,
                   as_of: str, currency: str = "AED", language: str | None = None) -> dict:
    """Write a reminder for one shop and save it as a draft for approval. Never sends anything.

    If the shop already has a draft waiting for approval, that draft is returned instead of a duplicate.
    """
    waiting = [d for d in list_drafts(store, "draft") if d["customer_id"] == customer_id]
    if waiting:
        return {**waiting[0], "already_existed": True}

    contact = get_customer_contact(billing, customer_id)
    channel = choose_channel(contact)
    if channel is None:
        raise ValueError(f"{contact['customer_name']} has no email or phone number on file")
    invoices = get_overdue_invoices(billing, customer_id, as_of)
    language = language or contact["language"]
    reminder = build_reminder(contact, invoices, language, currency)
    draft = create_draft(store, contact, reminder, language, channel[0], channel[1])
    return {**draft, "already_existed": False}