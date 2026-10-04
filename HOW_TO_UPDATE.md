# How to update this website

Every change is made on github.com in your browser. Open the file, click the pencil icon, edit, and click "Commit changes". The live site refreshes in about a minute.

## Add a project (no code)

Open `projects.json` and add an entry. Example with two projects:

```json
[
  {
    "title": "Sales Forecasting Pipeline",
    "description": "One or two sentences on what it does and what you built.",
    "tags": ["Python", "Airflow", "dbt"],
    "link": "https://github.com/AshokReddy010/your-repo",
    "image": "sales-forecast.png"
  },
  {
    "title": "Second project",
    "description": "Another short description.",
    "tags": ["Power BI"],
    "link": "https://github.com/AshokReddy010/another-repo"
  }
]
```

- `image` is optional. If you use it, upload that image file to this same folder ("Add file" > "Upload files").
- Separate entries with a comma, and keep the square brackets at the start and end.

The "On GitHub" section needs no editing: it lists your public repositories automatically.

## Replace your resume

Upload a new PDF named exactly `Ashok_Reddy_Bhimavarapu_Resume.pdf`. To refresh the on-page preview as well, replace `resume-page-1.png` and `resume-page-2.png` with images of the new pages.

## Replace your photo

Upload new files named `profile.jpg` (about 560 px square) and `profile-large.jpg` (about 1100 px square).

## Change text

Open `index.html`, press Ctrl+F to find the sentence, and edit it in place.

## Switch on the contact form

1. Sign up free at formspree.io with your Gmail and create a form. It gives you an address like `https://formspree.io/f/abcdwxyz`.
2. Open `index.html`, find `var FORM_ID = '';` and put the last part between the quotes: `var FORM_ID = 'abcdwxyz';`
3. Commit. Messages sent from the form now arrive in your Gmail.
