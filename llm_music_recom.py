import os
import json

import requests
import mpv
import youtube_search

AWANLLM_API_KEY = os.getenv("AWANLLM_API_KEY")
LASTFM_API_KEY = os.getenv("LASTFM_API_KEY")
LLM_SYSTEM_PROMPT = ("You are a helpful assistant who knows a lot about music."
                     " Your task is to execute users requests."
                     " If the user asks you to play something write a json"
                     " list with tracks that satisfy user description"
                     " in following format at the end of your reply"
                     ' [\n{\n"artist": "ARTIST_NAME",\n"track": "TRACK_NAME"\n}]')
print(AWANLLM_API_KEY)
print(LASTFM_API_KEY)


class AwanLLM:
    def __init__(self):
        self.messages = [
            {"role": "system", "content": LLM_SYSTEM_PROMPT},
        ]

    def request(self, content: str) -> str:
        url = "https://api.awanllm.com/v1/chat/completions"

        self.messages.append({"role": "user", "content": content})
        payload = json.dumps({
            "model": "Awanllm-Llama-3-8B-Dolfin",
            "messages": self.messages,
            "repetition_penalty": 1.1,
            "temperature": 0.7,
            "top_p": 0.9,
            "top_k": 40,
            "max_tokens": 1024,
            "stream": False
        })
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f"Bearer {AWANLLM_API_KEY}"
        }

        response = requests.request("POST", url, headers=headers, data=payload)
        res = response.json()["choices"][0]["message"]["content"]
        # print(res)
        return res


def parse_json_list(response: str) -> tuple[str, list, str] | None:
    start = response.find("[")
    end = response.rfind("]") + 1
    before = response[:start].strip("\n")
    after = response[end:].strip("\n")
    return before, json.loads(response[start:end]), after


def search_on_last_fm(track: str, artist: str) -> tuple[str, str] | None:
    url = f"http://ws.audioscrobbler.com/2.0/?method=track.search&track={
        track}&artist={artist}&api_key={LASTFM_API_KEY}&format=json"
    response = requests.request("GET", url).json()
    if matches := response["results"]["trackmatches"]["track"]:
        return matches[0]["name"], matches[0]["artist"]
    return None


def search_on_youtube(track: str, artist: str) -> str | None:
    results = youtube_search.YoutubeSearch(
        f"{track} - {artist}", max_results=1).to_dict()
    url = "https://www.youtube.com" + results[0]["url_suffix"]
    return url


def process(prompt: str, llm: AwanLLM, player: mpv.MPV) -> str:
    response = llm.request(prompt)
    before, recommendations, after = parse_json_list(response)
    res = [before, "\n"]
    for rec in recommendations:
        print(rec)
        track_artist = search_on_last_fm(rec["track"], rec["artist"])
        if not track_artist:
            continue
        track, artist = track_artist
        url = search_on_youtube(track, artist)
        player.loadfile(url, 'append-play')
        res.append(f"{artist} - {track} (link: {url})")
    res.extend(["\n", after])

    res = "\n".join(res)
    llm.messages.append({"role": "assistant", "content": res})
    return res


def main():
    player = mpv.MPV(ytdl=True, input_default_bindings=True,
                     input_vo_keyboard=True)
    llm = AwanLLM()
    player.playlist_pos = 0

    while True:
        print(process(input("> "), llm, player))
        print(player.playlist)


if __name__ == "__main__":
    main()
