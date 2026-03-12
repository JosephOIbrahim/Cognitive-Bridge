---
name: youtube2webpage
description: Convert YouTube videos into readable text webpages with screenshots and transcript. Use when the user wants to convert a YouTube video to text, extract a transcript with screenshots, or create a readable version of a video.
---

# Youtube2Webpage

## Overview

Converts YouTube videos into text-based webpages pairing closed captions with screenshots at each caption timestamp. Ideal for reading video content instead of watching it.

## When to Use

Use this skill when the user wants to:
- Convert a YouTube video into a readable webpage
- Extract a transcript with paired screenshots from a video
- Create a text version of a YouTube video
- Archive video content as a static webpage

## Usage

Run the Perl script with a project name and YouTube URL:

```bash
perl C:/Users/User/Youtube2Webpage/yt-to-webpage.pl <project-name> "<youtube-url>"
```

### Example

```bash
perl C:/Users/User/Youtube2Webpage/yt-to-webpage.pl houdini-tutorial "https://www.youtube.com/watch?v=jNQXAC9IVRw"
```

## Output

Creates a folder with this structure:

```
<project-name>/
  images/          -- screenshots at each caption timestamp (HH-MM-SS-mmm.jpg)
  video.vtt        -- closed captions file
  video.webm       -- downloaded video
  index.html       -- the generated webpage
  styles.css       -- styling
```

Open `index.html` in a browser to read the transcript with screenshots. Each caption line links back to the corresponding timestamp in the original video.

## Dependencies

All confirmed installed on this system:

| Tool | Version | Path |
|------|---------|------|
| **perl** | bundled | Git Bash `/usr/bin/perl` |
| **yt-dlp** | 2026.02.04 | `C:/Users/User/AppData/Roaming/Python/Python314/Scripts/yt-dlp.exe` |
| **ffmpeg** | 8.0.1 | WinGet package |

## Important Notes

- The script must be able to find `yt-dlp` and `ffmpeg` on PATH. If they aren't found, set PATH before running:
  ```bash
  export PATH="C:/Users/User/AppData/Roaming/Python/Python314/Scripts:C:/Users/User/AppData/Local/Microsoft/WinGet/Packages/Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe/ffmpeg-8.0.1-full_build/bin:$PATH"
  ```
- The script only accepts `https://www.youtube.com` URLs
- Video download size depends on available quality; captions require auto-generated or manual subs
- Screenshot extraction can take time for long videos (one ffmpeg call per caption line)

## Source

Repository: https://github.com/obra/Youtube2Webpage
License: MIT
