# Thoughtful AI Challenge, Search for news in LA News

## Running

#### VS Code

1. Get [Robocorp Code](https://robocorp.com/docs/developer-tools/visual-studio-code/extension-features) -extension for VS Code.

2. Click Run Task in the side menu

3. Select "search_soccer_news" as the input, or create a new work item in the same format of the `devdata/work-items-in/search_soccer_news` work item if you want a different input

#### Via Robocorp Control Room

1. Open the process at https://cloud.robocorp.com/nonekvcbh/robotsdevelopment/processes/bde66429-e8c5-491c-bdcd-451b986ad1e2 (needs to be in the Organization)

2. Select `Run process` and `Run with input data`

3. Add the desired search, for example

```json
{
  "phrase": "soccer",
  "category": "soccer",
  "last_months": 4
}
```

## Results

🚀 After running the bot, check the `output` folder for:

- The `log.html` file, which contains the execution log.
- The `news_images.zip` file, which includes all downloaded images.
- The `news.xlsx` file, which contains the news information.
