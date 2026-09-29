"""Synthetic 100-query eval set for Acme Helpdesk AI.

Each case has a deterministic rubric. Baseline outputs mimic the current models;
candidate outputs mimic the same-tier migrations in the sample savings report.
A few baseline answers fail on purpose so the quality gate has a real comparison.
"""

from __future__ import annotations

import json
from pathlib import Path

# (workload, baseline_model, candidate_model)
MODELS = {
    "proj_intent_router": ("gpt-5-mini", "gpt-6-luna"),
    "proj_support_chat": ("gpt-5.4", "gpt-6.1-sol"),
    "proj_ticket_summaries": ("gpt-4o", "gpt-6.1-sol"),
    "proj_sales_copilot": ("gpt-6-astra", "gpt-6-astra"),
    "wrkspc_rag_answers": ("claude-sonnet-4-5", "claude-sonnet-5-5"),
    "wrkspc_contract_review": ("claude-opus-4-1", "claude-opus-5-5"),
    "wrkspc_email_drafts": ("claude-haiku-4-5", "claude-haiku-4-5"),
}

# fail flags: B = baseline fails, C = candidate fails. Empty = both pass.
INTENTS: list[tuple[str, str, str]] = [
    ("password_reset", "I forgot my password and cannot log in", ""),
    ("password_reset", "The password reset email never arrived", ""),
    ("password_reset", "Reset my account password please", "BC"),
    ("billing_question", "Why was I charged twice on last month's invoice?", ""),
    ("billing_question", "The VAT line on invoice 4412 looks wrong", ""),
    ("billing_question", "Can you explain the seat overage on our bill?", ""),
    ("shipping_delay", "Order 1842 is five days late, where is it?", ""),
    ("shipping_delay", "Tracking for shipment 77-A still says label created", ""),
    ("shipping_delay", "The parcel to Berlin has not moved in a week", "B"),
    ("cancel_plan", "I want to cancel the Pro plan at the end of the month", ""),
    ("cancel_plan", "Please downgrade us to the free tier and stop billing", ""),
    ("bug_report", "The dashboard export button returns a 500 error", ""),
    ("bug_report", "CSV download of tickets is truncated after 100 rows", ""),
    ("bug_report", "SSO login loops back to the password screen", ""),
    ("feature_request", "Can we get a dark mode on the helpdesk inbox?", ""),
    ("feature_request", "We need a webhook when a ticket is escalated", ""),
    ("refund", "Order 2201 arrived damaged, I want a refund to the original card", ""),
    ("refund", "Charge 9981 was a duplicate, refund it please", "BC"),
    ("escalate", "This is the third time we write about the same outage", ""),
    ("escalate", "Please escalate ticket 551 to a manager today", ""),
    ("password_reset", "Unlock my account after too many failed logins", ""),
    ("shipping_delay", "Weekend delivery for order 3309 never happened", ""),
    ("cancel_plan", "We are leaving because the AI replies are too slow", ""),
    ("billing_question", "Did the annual discount apply on invoice 1204?", ""),
    ("feature_request", "Add Czech as a language for the ticket summaries", ""),
]

SUPPORT: list[tuple[str, str, list[str], str, str]] = [
    (
        "Order 1842 was charged twice. Refund the extra charge to the original card.",
        "I will refund the duplicate charge on order 1842 to the original card.",
        ["1842", "refund"],
        "I can look into your billing.",
        "BC",
    ),
    (
        "Ticket 551: customer cannot reset their password after SSO was enabled.",
        "For ticket 551, send a password reset from the SSO-linked account and confirm the identity provider mapping.",
        ["551", "password"],
        "",
        "",
    ),
    (
        "Shipment 77-A to Berlin is stuck. Give the customer a new ETA.",
        "Shipment 77-A to Berlin is delayed; share a new ETA and offer a credit if it slips.",
        ["77-A", "Berlin"],
        "",
        "",
    ),
    (
        "Invoice 4412 VAT looks wrong for a Czech company. What should we reply?",
        "Invoice 4412: confirm the Czech VAT ID, then reissue with the reverse-charge line if they are VAT registered.",
        ["4412", "VAT"],
        "",
        "",
    ),
    (
        "Order 2201 arrived damaged. Customer wants a refund, not a replacement.",
        "Approve a refund for damaged order 2201; do not ship a replacement unless they ask.",
        ["2201", "refund"],
        "Offer a replacement for the damaged parcel.",
        "B",
    ),
    (
        "Seat overage on the Pro plan: 42 seats billed, they only use 38.",
        "The Pro plan billed 42 seats; if 38 are active, remove the unused seats and credit the difference.",
        ["42", "38"],
        "",
        "",
    ),
    (
        "CSV export of tickets stops at 100 rows. Customer needs the full dump.",
        "The CSV export is capped at 100 rows; trigger a full ticket dump from the admin export job.",
        ["100", "export"],
        "",
        "",
    ),
    (
        "Customer on ticket 908 asked for Czech language summaries.",
        "On ticket 908, enable Czech as the summary language and regenerate the last replies.",
        ["908", "Czech"],
        "",
        "",
    ),
    (
        "Charge 9981 is a duplicate of 9980. Refund 9981.",
        "Refund duplicate charge 9981; leave 9980 in place.",
        ["9981", "refund"],
        "",
        "",
    ),
    (
        "Order 3309 weekend delivery never happened. What do we tell them?",
        "Order 3309 missed the weekend window; rebook delivery and add a shipping credit.",
        ["3309", "weekend"],
        "",
        "",
    ),
    (
        "SSO login loops back to the password screen for domain acme.cz.",
        "For acme.cz SSO, check the ACS URL; the password-screen loop is a misconfigured IdP.",
        ["acme.cz", "SSO"],
        "",
        "",
    ),
    (
        "Ticket 112 wants to cancel Pro at month end and keep data for 30 days.",
        "Cancel the Pro plan at month end for ticket 112 and keep the account data for 30 days.",
        ["112", "cancel"],
        "",
        "",
    ),
    (
        "Dashboard export button returns HTTP 500 for workspace wrk_9.",
        "The export button on workspace wrk_9 returns HTTP 500; file a bug and send a manual CSV meanwhile.",
        ["wrk_9", "500"],
        "",
        "",
    ),
    (
        "Customer asks if invoice 1204 includes the annual discount.",
        "Invoice 1204 should show the annual discount as a separate line; if missing, reissue it.",
        ["1204", "discount"],
        "",
        "",
    ),
    (
        "Escalate ticket 551 to a manager and mention the repeated outage.",
        "Escalate ticket 551 to a manager and note this is a repeated outage.",
        ["551", "outage"],
        "",
        "",
    ),
    (
        "Order 7720: customer paid, warehouse shows unpaid. Unblock shipment.",
        "Payment for order 7720 cleared; mark it paid in the warehouse system and unblock shipment.",
        ["7720", "paid"],
        "",
        "",
    ),
    (
        "Help the agent answer: refund policy is 14 days from delivery for order 640.",
        "Order 640 is inside the 14-day refund window from delivery; approve if unused.",
        ["640", "14-day"],
        "",
        "",
    ),
    (
        "Customer on ticket 77 reports the AI reply cited the wrong plan price.",
        "On ticket 77, correct the plan price in the AI reply and do not quote list prices without checking billing.",
        ["77", "price"],
        "",
        "",
    ),
]


def _summaries() -> list[tuple[str, str, list[str], str, str]]:
    rows = [
        (
            "Ticket: billing, charged twice on order 1842, wants refund, tone frustrated.",
            "Billing: duplicate charge on order 1842; customer wants a refund; tone frustrated.",
            ["1842", "refund"],
            "Customer asked about billing.",
            "BC",
        ),
        (
            "Ticket: shipping delay, order 3309, weekend slot missed, ask for credit.",
            "Shipping: order 3309 missed the weekend slot; customer asks for a credit.",
            ["3309", "weekend"],
            "",
            "",
        ),
        (
            "Ticket: SSO loop for acme.cz, cannot log in, already tried reset.",
            "Auth: SSO loop for acme.cz blocks login; password reset already tried.",
            ["acme.cz", "SSO"],
            "",
            "",
        ),
        (
            "Ticket: cancel Pro plan, keep data 30 days, reason slow AI replies.",
            "Cancel Pro, keep data 30 days; reason is slow AI replies.",
            ["cancel", "30 days"],
            "",
            "",
        ),
        (
            "Ticket: CSV export truncated at 100 rows, needs full dump today.",
            "Bug: CSV export truncates at 100 rows; full dump needed today.",
            ["100", "export"],
            "",
            "",
        ),
        (
            "Ticket: damaged order 2201, refund not replacement, photos attached.",
            "Damaged order 2201; customer wants a refund not a replacement; photos attached.",
            ["2201", "refund"],
            "",
            "",
        ),
        (
            "Ticket: invoice 4412 VAT for Czech company, reverse charge maybe.",
            "Invoice 4412 VAT query for a Czech company; reverse charge may apply.",
            ["4412", "VAT"],
            "",
            "",
        ),
        (
            "Ticket: feature request dark mode on inbox, 12 votes from the team.",
            "Feature request: dark mode on the inbox (12 team votes).",
            ["dark mode", "inbox"],
            "",
            "",
        ),
        (
            "Ticket: escalate 551, third contact about the same outage.",
            "Escalate ticket 551; third contact about the same outage.",
            ["551", "outage"],
            "",
            "",
        ),
        (
            "Ticket: charge 9981 duplicate of 9980, refund requested.",
            "Duplicate charge 9981 of 9980; refund requested.",
            ["9981", "refund"],
            "",
            "",
        ),
        (
            "Ticket: seat overage 42 billed vs 38 active on Pro.",
            "Seat overage: 42 billed, 38 active on Pro; credit the unused seats.",
            ["42", "38"],
            "",
            "",
        ),
        (
            "Ticket: export button HTTP 500 on workspace wrk_9.",
            "Bug: export button returns HTTP 500 on workspace wrk_9.",
            ["wrk_9", "500"],
            "",
            "",
        ),
        (
            "Ticket: Czech language for summaries, ticket 908.",
            "Request: Czech language summaries on ticket 908.",
            ["Czech", "908"],
            "",
            "",
        ),
        (
            "Ticket: invoice 1204 missing annual discount line.",
            "Invoice 1204 is missing the annual discount line.",
            ["1204", "discount"],
            "",
            "",
        ),
        (
            "Ticket: order 7720 paid in Stripe, warehouse still unpaid.",
            "Order 7720 is paid in Stripe but warehouse still shows unpaid.",
            ["7720", "paid"],
            "",
            "",
        ),
    ]
    return rows


def _rag() -> list[tuple[str, str, list[str], str, str]]:
    return [
        (
            "What is the refund window after delivery?",
            "Refunds are accepted within 14 days of delivery if the item is unused. Source: refund policy.",
            ["14 days", "delivery"],
            "You can return things if you change your mind.",
            "BC",
        ),
        (
            "How do we reverse-charge VAT for a Czech VAT-registered company?",
            "For a Czech VAT-registered buyer, issue reverse charge and no Czech VAT. Source: tax FAQ.",
            ["reverse charge", "VAT"],
            "",
            "",
        ),
        (
            "What is the SLA for Pro plan email replies?",
            "Pro plan email replies have a 4-hour business-hours SLA. Source: support SLA.",
            ["4-hour", "Pro"],
            "",
            "",
        ),
        (
            "Can we keep account data after a plan is cancelled?",
            "Cancelled accounts keep data for 30 days, then it is deleted. Source: retention policy.",
            ["30 days", "deleted"],
            "",
            "",
        ),
        (
            "When should a ticket be escalated to a manager?",
            "Escalate after two failed resolutions or on a repeated outage. Source: escalation playbook.",
            ["escalate", "outage"],
            "",
            "",
        ),
        (
            "Is weekend delivery guaranteed for orders placed on Friday?",
            "Weekend delivery is not guaranteed; Friday orders ship next business day. Source: shipping.",
            ["weekend", "not guaranteed"],
            "",
            "",
        ),
        (
            "How do unused seats get credited?",
            "Remove unused seats in billing; a credit appears on the next invoice. Source: seating guide.",
            ["unused seats", "credit"],
            "",
            "",
        ),
        (
            "What files can we attach to a damaged-goods claim?",
            "Attach photos of the parcel and item; claims without photos are delayed. Source: claims policy.",
            ["photos", "claims"],
            "",
            "",
        ),
        (
            "Does SSO replace passwords for every member?",
            "When SSO is enforced, members of that domain must sign in with SSO, not passwords. Source: SSO docs.",
            ["SSO", "passwords"],
            "",
            "",
        ),
        (
            "What is the export row limit in the dashboard?",
            "Dashboard CSV export is limited to 100 rows; use the admin full dump for more. Source: export docs.",
            ["100 rows", "export"],
            "",
            "",
        ),
        (
            "Which language can ticket summaries run in besides English?",
            "Summaries currently support English and Czech. Source: language settings.",
            ["Czech", "English"],
            "",
            "",
        ),
        (
            "Do annual plans show the discount as its own invoice line?",
            "Yes, the annual discount must appear as its own invoice line. Source: invoicing.",
            ["annual discount", "invoice"],
            "",
            "",
        ),
        (
            "What happens if Stripe says paid but warehouse says unpaid?",
            "Trust Stripe: mark paid, unblock shipment, then fix the warehouse flag. Source: payments.",
            ["Stripe", "warehouse"],
            "",
            "",
        ),
        (
            "Is a replacement the default for damaged orders?",
            "No. Offer a refund or replacement; refund if they refuse replacement. Source: claims.",
            ["refund", "replacement"],
            "",
            "",
        ),
        (
            "Where is the ACS URL for SAML?",
            "The SAML ACS URL is in organisation settings under SSO. Source: SSO docs.",
            ["ACS URL", "SSO"],
            "",
            "",
        ),
    ]


def _emails() -> list[tuple[str, str, list[str], str, str]]:
    return [
        (
            "Apologise for the delay on order 1842 and give a new Tuesday ETA.",
            "Sorry for the delay on order 1842. The new ETA is Tuesday; reply if that does not work.",
            ["1842", "Tuesday"],
            "Sorry for the wait, we are looking into it.",
            "BC",
        ),
        (
            "Confirm refund of charge 9981 to the original card.",
            "We refunded charge 9981 to the original card. It can take a few days to show on the statement.",
            ["9981", "refund"],
            "",
            "",
        ),
        (
            "Tell acme.cz we fixed the SSO loop and they can sign in again.",
            "The SSO loop for acme.cz is fixed. You can sign in again with your company identity provider.",
            ["acme.cz", "SSO"],
            "",
            "",
        ),
        (
            "Confirm Pro cancellation at month end and 30-day data retention.",
            "Your Pro plan will cancel at month end. We keep the data for 30 days if you change your mind.",
            ["cancel", "30 days"],
            "",
            "",
        ),
        (
            "Ask for photos for the damaged order 2201 claim.",
            "Please send photos of damaged order 2201 so we can process the claim.",
            ["2201", "photos"],
            "",
            "",
        ),
        (
            "Explain the 42 vs 38 seat overage and the coming credit.",
            "You were billed for 42 seats and 38 are active. We will credit the unused seats on the next invoice.",
            ["42", "credit"],
            "",
            "",
        ),
        (
            "Invite them to retry the CSV export after the 100-row cap is lifted.",
            "The 100-row CSV cap is lifted. Please retry the export; you should get the full ticket dump.",
            ["100", "export"],
            "",
            "",
        ),
        (
            "Confirm invoice 4412 will be reissued with reverse charge.",
            "Invoice 4412 will be reissued with reverse charge and no Czech VAT.",
            ["4412", "reverse charge"],
            "",
            "",
        ),
        (
            "Reassure them ticket 551 is with a manager because of the repeated outage.",
            "Ticket 551 is with a manager because this is a repeated outage. We will update you today.",
            ["551", "outage"],
            "",
            "",
        ),
        (
            "Confirm order 7720 is marked paid and will ship today.",
            "Order 7720 is marked paid and will ship today. Tracking follows once the label is created.",
            ["7720", "ship"],
            "",
            "",
        ),
        (
            "Tell them Czech summaries are on for ticket 908.",
            "Czech summaries are now on for ticket 908. Reload the ticket to see the new text.",
            ["Czech", "908"],
            "",
            "",
        ),
        (
            "Confirm the annual discount is now on invoice 1204.",
            "Invoice 1204 now includes the annual discount as its own line. A copy is attached.",
            ["1204", "discount"],
            "",
            "",
        ),
    ]


def _contracts() -> list[tuple[str, str, list[str], str, str]]:
    return [
        (
            "Flag the liability cap in clause 8.2 of this MSA.",
            "Clause 8.2 caps liability at 12 months of fees. Flag it before signing.",
            ["8.2", "liability"],
            "",
            "",
        ),
        (
            "Does clause 4 allow termination for convenience?",
            "Clause 4 allows termination for convenience with 30 days' notice.",
            ["clause 4", "30 days"],
            "",
            "",
        ),
        (
            "Is auto-renewal in the order form?",
            "The order form auto-renews for 12 months unless notice is given 60 days prior.",
            ["auto-renews", "60 days"],
            "",
            "",
        ),
        (
            "What data processing terms apply to EU customers?",
            "EU customers are covered by the DPA in schedule 2, including SCCs.",
            ["DPA", "SCCs"],
            "",
            "",
        ),
        (
            "Does the non-solicit last after the contract ends?",
            "The non-solicit survives for 12 months after the contract ends.",
            ["non-solicit", "12 months"],
            "",
            "",
        ),
        (
            "Highlight the payment term in clause 3.",
            "Clause 3 sets payment at net 30 from invoice date.",
            ["clause 3", "net 30"],
            "",
            "",
        ),
        (
            "Is there a most-favoured-customer clause?",
            "There is no most-favoured-customer clause in this draft.",
            ["no", "most-favoured"],
            "",
            "",
        ),
        (
            "What happens to fees if they terminate for cause?",
            "If they terminate for cause, prepaid fees for unused months are refunded.",
            ["for cause", "refunded"],
            "",
            "",
        ),
        (
            "Does clause 9 assign IP in custom prompts to the customer?",
            "Clause 9 assigns IP in custom prompts and eval sets to the customer.",
            ["clause 9", "customer"],
            "",
            "",
        ),
        (
            "Flag governing law.",
            "Governing law is England and Wales, courts of London. Flag if they expected Czech law.",
            ["England", "London"],
            "",
            "",
        ),
    ]


def _sales() -> list[tuple[str, str, list[str], str, str]]:
    return [
        (
            "Draft a one-liner why Pro is cheaper than three extra seats of Team.",
            "Pro is cheaper than three extra Team seats once you pass 38 people, because unused Team seats still bill.",
            ["Pro", "seats"],
            "",
            "",
        ),
        (
            "Counter a price objection: they compared us to a gateway dashboard.",
            "A gateway shows the bill; Pro proves quality on an eval set so the invoice drops.",
            ["eval set", "invoice"],
            "",
            "",
        ),
        (
            "Summarise the 14-day refund policy for a prospect who is nervous.",
            "If it is not unused after delivery, the 14-day refund does not apply; if it is, they get the money back.",
            ["14-day", "refund"],
            "",
            "",
        ),
        (
            "Propose a close: annual plan with the discount on its own invoice line.",
            "Close on the annual plan and show the discount as its own invoice line so finance can see it.",
            ["annual", "discount"],
            "",
            "",
        ),
        (
            "Reply to 'we already use Helicone'.",
            "Helicone is useful. It does not rewrite the calls or gate model changes with an eval. That is the gap.",
            ["Helicone", "eval"],
            "",
            "",
        ),
    ]


def _output(good: str, bad: str, fail: bool) -> str:
    if not fail:
        return good
    return bad or good.split(".")[0]


def _result(case_id: str, workload: str, output: str, which: str) -> dict:
    baseline, candidate = MODELS[workload]
    return {"id": case_id, "model": baseline if which == "baseline" else candidate, "output": output}


def build_eval_bundle() -> tuple[list[dict], list[dict], list[dict]]:
    cases: list[dict] = []
    baseline: list[dict] = []
    candidate: list[dict] = []

    def add(workload: str, case_id: str, prompt: str, checks: list[dict], good: str, bad: str, flags: str) -> None:
        cases.append({"id": case_id, "workload": workload, "input": prompt, "checks": checks})
        baseline.append(_result(case_id, workload, _output(good, bad, "B" in flags), "baseline"))
        candidate.append(_result(case_id, workload, _output(good, bad, "C" in flags), "candidate"))

    for i, (label, prompt, flags) in enumerate(INTENTS, 1):
        add(
            "proj_intent_router",
            f"intent_{i:03d}",
            prompt,
            [{"type": "exact", "value": label}],
            label,
            "billing_question" if label != "billing_question" else "bug_report",
            flags,
        )
    for i, (prompt, good, needles, bad, flags) in enumerate(SUPPORT, 1):
        add(
            "proj_support_chat",
            f"support_{i:03d}",
            prompt,
            [{"type": "contains_all", "value": needles}],
            good,
            bad,
            flags,
        )
    for i, (prompt, good, needles, bad, flags) in enumerate(_summaries(), 1):
        add(
            "proj_ticket_summaries",
            f"summary_{i:03d}",
            prompt,
            [{"type": "contains_all", "value": needles}],
            good,
            bad,
            flags,
        )
    for i, (prompt, good, needles, bad, flags) in enumerate(_rag(), 1):
        add(
            "wrkspc_rag_answers",
            f"rag_{i:03d}",
            prompt,
            [{"type": "contains_all", "value": needles}],
            good,
            bad,
            flags,
        )
    for i, (prompt, good, needles, bad, flags) in enumerate(_emails(), 1):
        add(
            "wrkspc_email_drafts",
            f"email_{i:03d}",
            prompt,
            [{"type": "contains_all", "value": needles}],
            good,
            bad,
            flags,
        )
    for i, (prompt, good, needles, bad, flags) in enumerate(_contracts(), 1):
        add(
            "wrkspc_contract_review",
            f"contract_{i:03d}",
            prompt,
            [{"type": "contains_all", "value": needles}],
            good,
            bad,
            flags,
        )
    for i, (prompt, good, needles, bad, flags) in enumerate(_sales(), 1):
        add(
            "proj_sales_copilot",
            f"sales_{i:03d}",
            prompt,
            [{"type": "contains_all", "value": needles}],
            good,
            bad,
            flags,
        )
    return cases, baseline, candidate


def write_eval_samples(out_dir: Path) -> list[Path]:
    cases, baseline, candidate = build_eval_bundle()
    if len(cases) != 100:
        raise ValueError(f"eval set must have 100 cases, got {len(cases)}")
    written = []
    for name, rows in (
        ("eval_set.jsonl", cases),
        ("eval_baseline.jsonl", baseline),
        ("eval_candidate.jsonl", candidate),
    ):
        path = out_dir / name
        path.write_text("".join(json.dumps(r) + "\n" for r in rows))
        written.append(path)
    return written
