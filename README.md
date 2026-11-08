# Club Reimbursement Tracker

A working prototype of a web portal where students submit club reimbursement claims and track each approval stage, and approvers approve or return claims in the app.

Built for the course Innovation & Entrepreneurship for Engineers, IIT Madras (Batch A, Group 15). Not affiliated with any IIT Madras system. All accounts and data are fictional.

## What it does

- Students submit a claim with club, purpose, amount, date and a receipt (PDF, JPG or PNG), and get a tracking ID such as `RMB-0001`.
- A five-step progress tracker shows where each claim is: Submitted, Faculty Advisor, Department, Accounts, Paid.
- Faculty advisors see an in-app notification for new claims and can approve, return for correction or reject, with a note.
- Department and Accounts approve in sequence, and Accounts records the payment.
- Every action is timestamped in the claim history.
- Dashboard cards show total, pending, approved and reimbursed claims for the logged-in student.
- A club treasurer gets read-only access to their club's claims.

## Tech

Python standard library (`http.server`) and SQLite. No external packages to install.

## Run it

Requires Python 3.9 or later.

```bash
git clone https://github.com/anandpattathil/Reimbursement-Tracker.git
cd Reimbursement-Tracker
python app.py
```

Open http://127.0.0.1:8000 in a browser. To use a different port, set `PORT`, for example `PORT=8080 python app.py`.

You can also run it in GitHub Codespaces: open the repo, choose Code > Codespaces > Create codespace, run `python app.py`, then open port 8000 from the Ports tab.

To clear all claims and receipts but keep the demo accounts, run `python reset_demo.py`.

## Demo accounts

| Role | Email | Password |
|---|---|---|
| Student | student@demo.local | Student123! |
| Faculty Advisor | faculty@demo.local | Faculty123! |
| Department | department@demo.local | Department123! |
| Accounts | accounts@demo.local | Accounts123! |
| Club Treasurer | treasurer@demo.local | Treasurer123! |
| Administrator | admin@demo.local | Admin123! |

The sign-in page also has one-click buttons for the Student and Faculty Advisor accounts. Set `DEMO_MODE=0` to turn them off.

## Try the main flow

1. Sign in as Student and submit a claim.
2. Sign out, sign in as Faculty Advisor, open the notification and approve the claim.
3. Sign back in as Student. The tracker now shows the claim at the Department stage.

## Limitations

- This is a prototype. Approvals and payments are simulated and no money moves.
- One account per approval stage. A real deployment would need per-department approvers, proper authentication and a privacy review.
- Do not enter real student or financial data.
