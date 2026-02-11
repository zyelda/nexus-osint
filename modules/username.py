import requests
from concurrent.futures import ThreadPoolExecutor

SITES = [
    {"name": "GitHub", "url": "https://github.com/{}", "error_msg": "Not Found"},
    {"name": "Instagram", "url": "https://www.instagram.com/{}/", "error_msg": "The link you followed may be broken"},
    {"name": "Twitter (X)", "url": "https://twitter.com/{}", "error_msg": "This account doesn’t exist"},
    {"name": "Facebook", "url": "https://www.facebook.com/{}", "error_msg": "This content isn't available right now"},
    {"name": "YouTube", "url": "https://www.youtube.com/@{}", "error_msg": "404 Not Found"},
    {"name": "TikTok", "url": "https://www.tiktok.com/@{}", "error_msg": "Couldn't find this account"},
    {"name": "Medium", "url": "https://medium.com/@{}", "error_msg": "404"},
    {"name": "Reddit", "url": "https://www.reddit.com/user/{}", "error_msg": "Sorry, nobody on Reddit goes by that name"},
    {"name": "Pinterest", "url": "https://www.pinterest.com/{}/", "error_msg": "User not found"},
    {"name": "SoundCloud", "url": "https://soundcloud.com/{}", "error_msg": "not found"},
    {"name": "Spotify", "url": "https://open.spotify.com/user/{}", "error_msg": "Page not found"},
    {"name": "Steam", "url": "https://steamcommunity.com/id/{}", "error_msg": "The specified profile could not be found"},
    {"name": "Vimeo", "url": "https://vimeo.com/{}", "error_msg": "404 Not Found"},
    {"name": "Wattpad", "url": "https://www.wattpad.com/user/{}", "error_msg": "User not found"},
    {"name": "Wikipedia", "url": "https://en.wikipedia.org/wiki/User:{}", "error_msg": "User account not found"},
    {"name": "Freelancer", "url": "https://www.freelancer.com/u/{}", "error_msg": "User not found"},
    {"name": "Kaggle", "url": "https://www.kaggle.com/{}", "error_msg": "404"},
    {"name": "GitLab", "url": "https://gitlab.com/{}", "error_msg": "Page Not Found"},
    {"name": "About.me", "url": "https://about.me/{}", "error_msg": "404"},
    {"name": "Pastebin", "url": "https://pastebin.com/u/{}", "error_msg": "Not Found"},
    {"name": "PyPI", "url": "https://pypi.org/user/{}", "error_msg": "404"},
    {"name": "Docker Hub", "url": "https://hub.docker.com/u/{}", "error_msg": "404"},
    {"name": "Replit", "url": "https://replit.com/@{}", "error_msg": "404"},
    {"name": "HackerRank", "url": "https://hackerrank.com/{}", "error_msg": "404"},
    {"name": "LeetCode", "url": "https://leetcode.com/{}", "error_msg": "page not found"},
    {"name": "CodePen", "url": "https://codepen.io/{}", "error_msg": "404"},
    {"name": "Dev.to", "url": "https://dev.to/{}", "error_msg": "404"},
    {"name": "StackOverflow", "url": "https://stackoverflow.com/users/{}", "error_msg": "Page not found"},
    {"name": "BitBucket", "url": "https://bitbucket.org/{}", "error_msg": "Resource not found"},
    {"name": "CodeWars", "url": "https://www.codewars.com/users/{}", "error_msg": "404"},
    {"name": "SourceForge", "url": "https://sourceforge.net/u/{}", "error_msg": "404"},
    {"name": "NPM", "url": "https://www.npmjs.com/~{}", "error_msg": "404"},
    {"name": "Packagist", "url": "https://packagist.org/users/{}/", "error_msg": "404"},
    {"name": "Behance", "url": "https://www.behance.net/{}", "error_msg": "404"},
    {"name": "Dribbble", "url": "https://dribbble.com/{}", "error_msg": "404"},
    {"name": "DeviantArt", "url": "https://www.deviantart.com/{}", "error_msg": "404"},
    {"name": "ArtStation", "url": "https://www.artstation.com/{}", "error_msg": "404"},
    {"name": "Unsplash", "url": "https://unsplash.com/@{}", "error_msg": "404"},
    {"name": "Flickr", "url": "https://www.flickr.com/people/{}", "error_msg": "404"},
    {"name": "500px", "url": "https://500px.com/p/{}", "error_msg": "404"},
    {"name": "Giphy", "url": "https://giphy.com/channel/{}", "error_msg": "404"},
    {"name": "VSCO", "url": "https://vsco.co/{}", "error_msg": "404"},
    {"name": "Coroflot", "url": "https://www.coroflot.com/{}", "error_msg": "404"},
    {"name": "Crevado", "url": "https://crevado.com/{}", "error_msg": "404"},
    {"name": "Tumblr", "url": "https://{}.tumblr.com", "error_msg": "Not Found"},
    {"name": "Mastodon (Social)", "url": "https://mastodon.social/@{}", "error_msg": "404"},
    {"name": "VK (Russia)", "url": "https://vk.com/{}", "error_msg": "404"},
    {"name": "OK.ru", "url": "https://ok.ru/{}", "error_msg": "404"},
    {"name": "Telegram", "url": "https://t.me/{}", "error_msg": "tgme_page_title"},
    {"name": "Linktree", "url": "https://linktr.ee/{}", "error_msg": "404"},
    {"name": "Carrd", "url": "https://{}.carrd.co", "error_msg": "404"},
    {"name": "Patreon", "url": "https://www.patreon.com/{}", "error_msg": "404"},
    {"name": "Ko-fi", "url": "https://ko-fi.com/{}", "error_msg": "404"},
    {"name": "BuyMeACoffee", "url": "https://www.buymeacoffee.com/{}", "error_msg": "404"},
    {"name": "Clubhouse", "url": "https://www.clubhouse.com/@{}", "error_msg": "404"},
    {"name": "AskFM", "url": "https://ask.fm/{}", "error_msg": "404"},
    {"name": "Tellonym", "url": "https://tellonym.me/{}", "error_msg": "404"},
    {"name": "WordPress", "url": "https://{}.wordpress.com", "error_msg": "doesn’t exist"},
    {"name": "Blogger", "url": "https://{}.blogspot.com", "error_msg": "404"},
    {"name": "Ghost", "url": "https://{}.ghost.io", "error_msg": "404"},
    {"name": "Substack", "url": "https://{}.substack.com", "error_msg": "404"},
    {"name": "Wix", "url": "https://{}.wixsite.com/website", "error_msg": "404"},
    {"name": "Weebly", "url": "https://{}.weebly.com", "error_msg": "404"},
    {"name": "LiveJournal", "url": "https://{}.livejournal.com", "error_msg": "404"},
    {"name": "SlideShare", "url": "https://www.slideshare.net/{}", "error_msg": "404"},
    {"name": "Issuu", "url": "https://issuu.com/{}", "error_msg": "404"},
    {"name": "Scribd", "url": "https://www.scribd.com/user/{}/", "error_msg": "404"},
    {"name": "GoodReads", "url": "https://www.goodreads.com/user/show/{}", "error_msg": "404"},
    {"name": "Twitch", "url": "https://www.twitch.tv/{}", "error_msg": "content_unavailable"},
    {"name": "Roblox", "url": "https://www.roblox.com/user.aspx?username={}", "error_msg": "404"},
    {"name": "Minecraft (NameMC)", "url": "https://namemc.com/profile/{}", "error_msg": "404"},
    {"name": "Chess.com", "url": "https://www.chess.com/member/{}", "error_msg": "404"},
    {"name": "Lichess", "url": "https://lichess.org/@/{}", "error_msg": "404"},
    {"name": "Speedrun", "url": "https://www.speedrun.com/user/{}", "error_msg": "404"},
    {"name": "Osu!", "url": "https://osu.ppy.sh/users/{}", "error_msg": "404"},
    {"name": "Kongregate", "url": "https://www.kongregate.com/accounts/{}", "error_msg": "404"},
    {"name": "Itch.io", "url": "https://{}.itch.io", "error_msg": "404"},
    {"name": "Newgrounds", "url": "https://{}.newgrounds.com", "error_msg": "404"},
    {"name": "GOG", "url": "https://www.gog.com/u/{}", "error_msg": "404"},
    {"name": "Bandcamp", "url": "https://bandcamp.com/{}", "error_msg": "404"},
    {"name": "Last.fm", "url": "https://www.last.fm/user/{}", "error_msg": "404"},
    {"name": "Mixcloud", "url": "https://www.mixcloud.com/{}", "error_msg": "404"},
    {"name": "Discogs", "url": "https://www.discogs.com/user/{}", "error_msg": "404"},
    {"name": "ReverbNation", "url": "https://www.reverbnation.com/{}", "error_msg": "404"},
    {"name": "AudioJungle", "url": "https://audiojungle.net/user/{}", "error_msg": "404"},
    {"name": "Fiverr", "url": "https://www.fiverr.com/{}", "error_msg": "404"},
    {"name": "Upwork", "url": "https://www.upwork.com/freelancers/~{}", "error_msg": "404"},
    {"name": "Hubstaff", "url": "https://talent.hubstaff.com/{}", "error_msg": "404"},
    {"name": "Contra", "url": "https://contra.com/{}", "error_msg": "404"},
    {"name": "Etsy", "url": "https://www.etsy.com/shop/{}", "error_msg": "404"},
    {"name": "eBay", "url": "https://www.ebay.com/usr/{}", "error_msg": "404"},
    {"name": "Mercari", "url": "https://www.mercari.com/u/{}", "error_msg": "404"},
    {"name": "Poshmark", "url": "https://poshmark.com/closet/{}", "error_msg": "404"},
    {"name": "Gumroad", "url": "https://gumroad.com/{}", "error_msg": "404"},
    {"name": "Redbubble", "url": "https://www.redbubble.com/people/{}", "error_msg": "404"},
    {"name": "Wikipedia (User)", "url": "https://en.wikipedia.org/wiki/User:{}", "error_msg": "404"},
    {"name": "ProductHunt", "url": "https://www.producthunt.com/@{}", "error_msg": "404"},
    {"name": "HackerNews", "url": "https://news.ycombinator.com/user?id={}", "error_msg": "No such user"},
    {"name": "Quora", "url": "https://www.quora.com/profile/{}", "error_msg": "404"},
    {"name": "SlideShare", "url": "https://www.slideshare.net/{}", "error_msg": "404"},
    {"name": "Keybase", "url": "https://keybase.io/{}", "error_msg": "404"},
    {"name": "Gravatar", "url": "http://en.gravatar.com/{}", "error_msg": "404"},
    {"name": "Disqus", "url": "https://disqus.com/by/{}", "error_msg": "404"},
    {"name": "IFTTT", "url": "https://ifttt.com/p/{}", "error_msg": "404"},
    {"name": "TripAdvisor", "url": "https://www.tripadvisor.com/members/{}", "error_msg": "404"},
    {"name": "9GAG", "url": "https://9gag.com/u/{}", "error_msg": "404"},
    {"name": "Imgur", "url": "https://imgur.com/user/{}", "error_msg": "404"},
    {"name": "Flipboard", "url": "https://flipboard.com/@{}", "error_msg": "404"},
    {"name": "Giphy", "url": "https://giphy.com/channel/{}", "error_msg": "404"},
    {"name": "Pastebin", "url": "https://pastebin.com/u/{}", "error_msg": "404"},
    {"name": "HubPages", "url": "https://hubpages.com/@{}", "error_msg": "404"},
    {"name": "BuzzFeed", "url": "https://www.buzzfeed.com/{}", "error_msg": "404"},
    {"name": "DailyMotion", "url": "https://www.dailymotion.com/{}", "error_msg": "404"},
    {"name": "VirusTotal", "url": "https://www.virustotal.com/gui/user/{}", "error_msg": "404"},
    {"name": "Trello", "url": "https://trello.com/{}", "error_msg": "404"},
    {"name": "Slack (Community)", "url": "https://{}.slack.com", "error_msg": "404"},
    {"name": "Prezi", "url": "https://prezi.com/user/{}", "error_msg": "404"},
    {"name": "Venmo", "url": "https://venmo.com/{}", "error_msg": "404"},
    {"name": "CashApp", "url": "https://cash.app/${}", "error_msg": "404"},
    {"name": "MyAnimeList", "url": "https://myanimelist.net/profile/{}", "error_msg": "404"},
    {"name": "Anime-Planet", "url": "https://www.anime-planet.com/users/{}", "error_msg": "404"},
    {"name": "Letterboxd", "url": "https://letterboxd.com/{}", "error_msg": "404"},
    {"name": "Trakt", "url": "https://trakt.tv/users/{}", "error_msg": "404"}
]

def check_site(site, username):
    target_url = site["url"].format(username)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    try:
        response = requests.get(target_url, headers=headers, timeout=5)
        if response.status_code == 200:
            if site["error_msg"] in response.text:
                return None
            return {"site": site["name"], "url": target_url, "status": "FOUND"}
        else:
            return None

    except:
        return None

def scan_username_profiles(username):
    found_accounts = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(check_site, site, username) for site in SITES]
        
        for future in futures:
            result = future.result()
            if result:
                found_accounts.append(result)

    return found_accounts