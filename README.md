# Club Reimbursement Tracker (Academic Demonstration)

A real, browser-based workflow demonstration using **Python standard library + SQLite + HTML/CSS**. No Flask, pip packages, real payments, or IIT Madras integration.

## Run in GitHub Codespaces (no local installs)

1. Create a **private** GitHub repository and upload the contents of this folder through **Add file > Upload files**.
2. From the repository, choose **Code > Codespaces > Create codespace on main**.
3. In the Codespaces terminal, run `python app.py` (or `python3 app.py`).
4. In **Ports**, open port **8000** in a browser. Keep its visibility **Private**.
5. Use the fictional login credentials below. Keep the Codespace running during the video.

If port 8000 isn't detected automatically, open the Codespaces **Ports** tab and add port 8000. If an old database exists after updates, use `python reset_demo.py` to clear fictional claims, then restart.

## Demo accounts

| Role | Email | Password |
|---|---|---|
| Student | student@demo.local | Student123! |
| Faculty Advisor | faculty@demo.local | Faculty123! |
| Department | department@demo.local | Department123! |
| Accounts | accounts@demo.local | Accounts123! |
| Club Treasurer | treasurer@demo.local | Treasurer123! |
| Administrator | admin@demo.local | Admin123! |

**These are fictional, well-known demonstration credentials. Never put actual student information in this app or expose its port publicly.**

## Suggested 3-minute recording

1. Sign in as Student. Select **Submit Claim**. Enter "Robotics Club", "Event supplies", and "3500". Optionally upload a fictional PNG/JPG/PDF receipt.
2. Submit and show the assigned ID, such as `RMB-0001`, and the **Faculty Advisor Pending** status.
3. Sign out. Sign in as Faculty Advisor. Open the new claim, inspect the receipt, and select **Approve**.
4. Sign out and log back in as Student. Open the same claim and show **Department Pending** and the timestamped approval history.

Additional features implemented include Department and Accounts sequential approvals, payment recording, return-for-correction, rejection, claim search, club treasurer read-only access, and basic demo analytics. The browser refreshes an inactive claim/dashboard view periodically.

## Important limitations

- This is a **local/classroom demonstration** with simulated approvals and simulated payment records.
- It is **not** production-ready, not affiliated with IIT Madras, and does not process payments.
- Demo account passwords are published in this README because the project is intentionally fictional and disposable.
- Approval scopes are simplified to one user per institution-wide approval stage. Production would require finer-grained stage assignments, secure authentication and deployment hardening.
- No academic baseline or 10x improvement is claimed or measured in the application.

## Reset demo claims

Run `python reset_demo.py`. This clears claims, actions and uploaded receipts, while retaining the demo accounts.

A fictional PDF receipt is provided at `demo_assets/sample_receipt.pdf` for the video. Select it using the receipt upload field when submitting the claim.
