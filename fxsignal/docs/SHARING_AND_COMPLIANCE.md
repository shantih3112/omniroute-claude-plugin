# Sharing the feed with others — controls and open legal questions

Nothing here is legal advice. The service is private and admin-only; no one has been invited,
nothing is published, and nothing is charged. None of that changes without your explicit instruction.

## Built-in controls
* **Separation**: admin bot chat (commands + research output) · broadcast channel (only
  strategies at `paper_forward` or better) · optional discussion group with no bot authority.
* **Authorisation**: commands only from numeric IDs in `TELEGRAM_ADMIN_IDS`; others get no reply.
* **No personal data in the channel**: messages show illustrative risk %, never your balance,
  positions, account size or credentials. `/size` replies only in a private chat.
* **One canonical record**: every recipient gets text rendered from the same immutable DB row;
  updates reference the signal ID; nothing is edited or deleted.
* **Stale protection**: signals carry expiry and an entry zone; late recipients see "do not chase".
* **Delivery honesty**: "accepted by Telegram API" is reported, never "read" or "received".

## Inviting people later (procedure)
1. Use a private channel. Create per-person invite links with `createChatInviteLink`
   (`member_limit=1`, `expire_date`) so each link is traceable; revoke with `revokeChatInviteLink`.
2. Remove access with `banChatMember` (then `unbanChatMember` if they should be able to rejoin later).
3. Keep a simple recipient register (who, when invited, link used, when removed).
These calls are not wired to commands yet, deliberately: invitations need your decision each time.

## Regulatory questions to settle BEFORE any public or paid launch
| Question | What we found (2026-10-20) | Action |
|---|---|---|
| Does a signal feed count as an "investment recommendation" under EU/EEA MAR (Art. 3(1)(35))? | ESMA treats the definition broadly and applies it to social media by substance, not label; price targets can implicitly recommend a strategy. Obligations include objective presentation and disclosure of interests/conflicts (Delegated Reg. 2016/958) — ESMA74-1103241886-912 (2024). MAR covers *financial instruments*: spot FX is generally outside, but **FX CFDs (what retail brokers and FTMO offer) are financial instruments**. | Get a Norwegian lawyer's opinion on which instruments and wording are in scope |
| Is it regulated investment advice (MiFID II, Norwegian Securities Trading Act)? | Personalised recommendations are investment advice; general publications generally are not, but the line depends on facts. Finanstilsynet has issued 2026 warnings against unauthorised firms marketing "signals" and trading education. No Norwegian rule specific to Telegram signal groups was found. | Ask Finanstilsynet or counsel before charging or advertising |
| Other jurisdictions of recipients | Some regulators (e.g. South Africa's FSCA) treat signal provision as a licensed financial service and have fined Telegram signal providers. | Restrict to known jurisdictions; check each |
| Consumer/marketing law | Performance claims must be fair and not misleading; hypothetical vs paper vs live must be distinguished (the system already labels them). | Keep all published performance labelled and complete |
| Telegram terms | Bot and channel usage subject to Telegram's ToS. | Review before monetising |

Sources: ESMA statement ESMA74-1103241886-912 "Warnings on Social Media and Investment
Recommendations" (Feb 2024); ESMA MAR Q&A; Finanstilsynet investor alerts 2026
(finanstilsynet.no/en/investor-alerts/2026/…); Finance Magnates / Moonstone reports on FSCA
enforcement against an unlicensed Telegram signal provider.
