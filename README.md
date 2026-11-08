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

## New in the visually refreshed version

- Spacious blue-and-white dashboard with improved typography, padding, form controls, claim tables, and approval timeline.
- **Faculty Advisor in-portal alerts:** Whenever a student creates a reimbursement claim, the Faculty Advisor dashboard shows an attention banner and a bell-style **Notifications** link with the number of claims awaiting review. Click **Notifications** for direct links to those claims.
- The alert count is recalculated from SQLite every time the page loads and disappears after the faculty approves, returns or rejects the claim. It is **not** an email, WhatsApp message, desktop push notification or a system-level popup. It is shown when the Faculty Advisor visits or refreshes the portal. Active dashboards automatically refresh during inactivity.
- No software packages or notification service setup needed.

### Updating an existing GitHub repository

If you previously uploaded version 1, replace `app.py` and `static/style.css` with the new copies, and optionally replace this README. Keep the `static` folder structure unchanged. In Codespaces, stop the current server with Ctrl+C, then run `python app.py` again. Your previous fictional claims remain in SQLite, unless you explicitly reset them with `python reset_demo.py`.

## Suggested 3-minute recording

1. Sign in as Student. Select **Submit Claim**. Enter "Robotics Club", "Event supplies", and "3500". Optionally upload a fictional PNG/JPG/PDF receipt.
2. Submit and show the assigned ID, such as `RMB-0001`, and the **Faculty Advisor Pending** status.
3. Sign out. Sign in as Faculty Advisor. **Show the new notification banner and bell counter**, click **Notifications**, open the claim, inspect the receipt, and select **Approve**.
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

## Version 3: Video-ready interface (new)

This version adds all improvements chosen after the notification update:

- **Five-step progress tracker:** Submitted, Faculty Advisor, Department, Accounts, Paid. Green indicates complete, blue the current stage and grey upcoming steps. Returned and rejected claims are shown as stopped rather than falsely completed. Shown on the latest claim panel of the student dashboard and every claim detail page.
- **Demo Quick Login:** On the sign-in screen, choose **Continue as Student** or **Continue as Faculty Advisor**. These fixed demo-account shortcuts work only when `DEMO_MODE=1` (the default for this academic project). Use **Sign out** between roles.
- **Faculty approval confirmation:** A successful faculty approval displays a dedicated confirmation with claim ID, amount, timestamp, new Department Pending status and a **View Claim & Timeline** action.
- **Four real-time student summary cards:** Total Claims, Pending Approval, Approved (all approvals received, awaiting payment), and Reimbursed (paid). Counts are computed from SQLite for the logged-in student. Returned or rejected claims remain in Total Claims but are not counted as pending.
- **Friendly no-claims experience:** All counts start at zero, with a **Create First Claim** call to action. There is no need to preload claim data for the video.
- **Claim submission confirmation:** New submissions lead to a dedicated screen with the generated claim ID, amount, submission timestamp, Faculty Advisor Pending status and a **Track My Claim** action.
- The visual refresh, extra whitespace, notification bell and Faculty Advisor inbox from version 2 remain included.

### Short version 3 filming route

1. Open the login screen and press **Continue as Student**. Show the empty dashboard and four zero-value summary cards.
2. Press **Create First Claim**. Enter `Robotics Club`, `Event supplies`, `3500`, today's date, and (optionally) `demo_assets/sample_receipt.pdf`. Submit.
3. Show the **Claim submitted successfully** screen and click **Track My Claim**. Show the progress tracker with Faculty Advisor as the active stage.
4. **Sign out**, then press **Continue as Faculty Advisor**. Open the Notifications bell, select the pending claim, and click **Approve**.
5. Show the **Claim approved successfully** screen with Department Pending. **Sign out**, quick-login as Student and show the updated dashboard progress and timestamped claim history.

### Updating an existing repository from v2

Upload the updated **`app.py`**, **`static/style.css`** and **`README.md`** to the same relative paths in the private GitHub repository and commit. Do not upload any files from the local `instance/` directory. If you want the previously generated claim history in your existing Codespace, leave its `instance/` directory alone. To film from an empty dashboard, use `python reset_demo.py` in the Codespaces terminal, which intentionally deletes *fictional demo claims and uploads*. Stop the old server with Ctrl+C and run `python app.py` to start the new code. You do not need to install Python packages.

**Security note:** Quick login bypasses passwords intentionally for fictional classroom demo accounts. Never turn it on for a public or real-data deployment. Keep the Codespaces forwarded port private and never use real personal, financial, or institutional records.
