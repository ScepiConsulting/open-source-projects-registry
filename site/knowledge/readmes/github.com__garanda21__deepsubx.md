
# DeepSubX

DeepSubX is a Dockerized application that uses the DeepL API to translate subtitles for TV shows and movies in your library. Additionally, it can extract embedded subtitles from video files and translate them into the desired language. 

The application offers optional integration with a Plex server, allowing you to update your Plex library automatically once the subtitles are translated.

![CleanShot 2024-12-31 at 11 55 21@2x](https://github.com/user-attachments/assets/908c2459-608b-4a5a-b772-ae5bc78b50a8)

---

## Features

- Translate subtitles for TV shows and movies using DeepL.
- Extract embedded subtitles and translate them.
- Optional Plex server integration for automatic library updates.

---

## Requirements

1. Docker installed on your system.
2. A DeepL API key.
3. Mapped directories for movies and TV shows:
   - `./data:/data`
   - `./movies:/movies`
4. Optional: Plex host, port, and token for library updates.

---

## Folder Structure

- **Movies:** Each movie should be in its folder.  
  Example:  
  ```
  /movies
    /Movie 1
      file1.mkv
      file1.srt
    /Movie 2
      file2.mkv
      file2.srt
  ```
  
- **TV Shows:** Organized into show and season folders.  
  Example:  
  ```
  /TV Show
    /Season 1
      episode1.mkv
      episode1.srt
  ```

---

## Environment Variables

| Variable       | Description                               | Required |
|----------------|-------------------------------------------|----------|
| `DEEPL_API_KEY` | Your DeepL API key                        | Yes      |
| `PLEX_HOST`     | Plex server hostname or IP address         | Optional |
| `PLEX_PORT`     | Plex server port                          | Optional |
| `PLEX_TOKEN`    | Plex API token                            | Optional |

---

## How to Get a DeepL API Key

1. Visit [DeepL's website](https://www.deepl.com/pro-api).
2. Sign up for an account or log in.
3. Navigate to the API section and generate an API key.
4. Copy the key and use it in the `DEEPL_API_KEY` environment variable.

---

## How to Get a Plex Token

1. Open your Plex server in a browser and log in.
2. Right-click anywhere on the page and select "Inspect" (or press `Ctrl+Shift+I`).
3. Go to the "Network" tab and reload the page.
4. Search for `X-Plex-Token` in the request headers.
5. Copy the token and use it in the `PLEX_TOKEN` environment variable.

For detailed instructions, refer to the official [Plex Token Documentation](https://support.plex.tv/articles/204059436-finding-an-authentication-token-x-plex-token/).

---

## Running the Application

1. Clone the repository:
   ```bash
   git clone https://github.com/garanda21/deepsubx.git
   ```
2. Navigate to the project directory:
   ```bash
   cd deepsubx
   ```
3. Set up the `.env` file with the required variables:
   ```env
   DEEPL_API_KEY=<your_deepl_api_key>
   PLEX_HOST=<optional_plex_host>
   PLEX_PORT=<optional_plex_port>
   PLEX_TOKEN=<optional_plex_token>
   ```
4. Start the application with Docker Compose:
   ```bash
   docker-compose up --build
   ```
5. Optionally you can use the `docker-compose.yml` at the root of the project
---

## Optional Plex Integration

If configured, DeepSubX can notify Plex to update its library after subtitles are translated. This step is optional and does not affect the main functionality.

---

## Tech Stack

- **Frontend:** Vite, React, Tailwind CSS
- **Backend:** Node.js
- **Containerization:** Docker

---

## License

This project is licensed under the [MIT License](LICENSE).

---

## Contributing

Contributions are welcome! Please open an issue or submit a pull request for any improvements or fixes.
