#by @bunnykek
import re
from utils.models import *
from utils.utils import create_temp_filename, create_requests_session
import html


CLEANR = re.compile('<.*?>') 

def cleanhtml(raw_html):
  cleantext = re.sub(CLEANR, '', raw_html)
  return cleantext

module_information = ModuleInformation( # Only service_name and module_supported_modes are mandatory
    service_name = 'Jiosaavn',
    module_supported_modes = ModuleModes.download | ModuleModes.lyrics | ModuleModes.covers | ModuleModes.credits,
    flags = ModuleFlags.hidden,
    global_settings = {},
    global_storage_variables = [],
    session_settings = {},
    session_storage_variables = [],
    netlocation_constant = 'jiosaavn', 
    test_url = 'https://www.jiosaavn.com/song/hua-main/Fl8HXENfU1c',
    
    url_constants = { # This is the default if no url_constants is given. Unused if custom_url_parsing is flagged
        'song': DownloadTypeEnum.track,
        'album': DownloadTypeEnum.album,
        'featured': DownloadTypeEnum.playlist,
        'artist': DownloadTypeEnum.artist
    }, # How this works: if '/track/' is detected in the URL, then track downloading is triggered
    login_behaviour = ManualEnum.manual, # setting to ManualEnum.manual disables Orpheus automatically calling login() when needed
    url_decoding = ManualEnum.orpheus # setting to ManualEnum.manual disables Orpheus' automatic url decoding which works as follows:
    # taking the url_constants dict as a list of constants to check for in the url's segments, and the final part of the URL as the ID
)


class ModuleInterface:
    def __init__(self, module_controller: ModuleController):
        self.session = create_requests_session()
        self.module_controller = module_controller

        self.quality_parse = {
            QualityEnum.MINIMUM: 'AAC_96',
            QualityEnum.LOW: 'AAC_96',
            QualityEnum.MEDIUM: 'AAC_160',
            QualityEnum.HIGH: 'AAC_320',
            QualityEnum.LOSSLESS: 'AAC_320',
            QualityEnum.HIFI: 'AAC_320'
        }

        self.song_api = "https://www.jiosaavn.com/api.php?__call=webapi.get&token={}&type=song&_format=json"
        self.album_api = "https://www.jiosaavn.com/api.php?__call=webapi.get&token={}&type=album&_format=json"
        self.playlist_api = "https://www.jiosaavn.com/api.php?__call=webapi.get&token={}&type=playlist&_format=json"
        self.lyrics_api = "https://www.jiosaavn.com/api.php?__call=lyrics.getLyrics&ctx=web6dot0&api_version=4&_format=json&_marker=0%3F_marker%3D0&lyrics_id="
        self.album_song_rx = re.compile(r"https://www\.jiosaavn\.com/(album|song)/.+?/(.+)")
        self.playlist_rx = re.compile(r"https://www\.jiosaavn\.com/featured/.+/(.+)")



    def get_playlist_json(self, playlist_id: str) -> dict:
        playlist_json = self.session.get(self.playlist_api.format(playlist_id)).json()
        return playlist_json

    def get_playlist_info(self, playlist_id: str, data={}) -> PlaylistInfo:  # Mandatory if either ModuleModes.download or ModuleModes.playlist
        playlist_data = data[playlist_id] if playlist_id in data else self.get_playlist_json(playlist_id)

        return PlaylistInfo(
            name = playlist_data['listname'],
            creator = '',
            tracks = [self.album_song_rx.search(song['perma_url']).group(2) for song in playlist_data['songs']],
            release_year = '',
            explicit = False,
            creator_id = '', # optional
            cover_url =  playlist_data['image'], # optional
            cover_type = ImageFileTypeEnum.jpg, # optional
            animated_cover_url = '', # optional
            description = '', # optional
            track_extra_kwargs = {
                'data':{self.album_song_rx.search(song['perma_url']).group(2): song for song in playlist_data['songs']}
            } # optional, whatever you want
        )
    

    def get_album_json(self, album_id: str) -> dict:
        album_json = self.session.get(self.album_api.format(album_id)).json()
        return album_json
    
    
    def get_album_info(self, album_id: str, data={}) -> Optional[AlbumInfo]: # Mandatory if ModuleModes.download
        album_data = data[album_id] if album_id in data else self.get_album_json(album_id)

        track_extra_kwargs = {'data' : {self.album_song_rx.search(song['perma_url']).group(2): song for song in album_data['songs']} }
        track_extra_kwargs['data']['album_artist']=html.unescape(album_data['primary_artists']),
        track_extra_kwargs['data']['total_tracks']=len(album_data['songs']),
        track_extra_kwargs['data']['track_no'] = {self.album_song_rx.search(song['perma_url']).group(2): i+1 for i, song in enumerate(album_data['songs'])},
        

        return AlbumInfo(
            name = html.unescape(album_data['name']),
            artist = html.unescape(album_data['primary_artists']),
            tracks = [self.album_song_rx.search(song['perma_url']).group(2) for song in album_data['songs']],
            release_year = album_data['year'],
            explicit = '',
            artist_id = album_data['primary_artists_id'], # optional
            booklet_url = '', # optional
            cover_url = album_data['image'].replace('150', '500'), # optional
            cover_type = ImageFileTypeEnum.jpg, # optional
            all_track_cover_jpg_url = '', # technically optional, but HIGHLY recommended
            animated_cover_url = '', # optional
            description = '', # optional
            track_extra_kwargs = track_extra_kwargs
        )
    
    def get_track_json(self, song_id: str) -> dict:
        metadata = self.session.get(self.song_api.format(song_id)).json()
        song_json = metadata[f'{list(metadata.keys())[0]}']
        return song_json


    def get_track_info(self, track_id: str, quality_tier: QualityEnum, codec_options: CodecOptions, data={}) -> TrackInfo: # Mandatory
        track_data =  data[track_id] if data and track_id in data else self.get_track_json(track_id)
        # print(json.dumps(data, indent=2))   
        tags = Tags( # every single one of these is optional
            album_artist = data['album_artist'] if data and 'album_artist' in data else track_data['primary_artists'].split(', '),
            composer = html.unescape(track_data['music']),
            track_number = data['track_no'][0][track_id] if data and 'track_no' in data else 1,
            total_tracks = data['total_tracks'][0] if data and 'total_tracks' in data else 1,
            copyright = html.unescape(track_data['copyright_text']),
            isrc = '',
            upc = '',
            disc_number = 1, # None/0/1 if no discs
            total_discs = 1, # None/0/1 if no discs
            replay_gain = 0.0,
            replay_peak = 0.0,
            genres = [],
            release_date = track_data['release_date'] # Format: YYYY-MM-DD
        )

        return TrackInfo(
            name = html.unescape(track_data['song']),
            album_id = track_data['albumid'],
            album = html.unescape(track_data['album']),
            artists = html.unescape(track_data['primary_artists']).split(', '),
            tags = tags,
            codec = CodecEnum.AAC,
            cover_url = track_data['image'].replace('150', '500'), # make sure to check module_controller.orpheus_options.default_cover_options
            release_year = track_data['year'],
            explicit = True if track_data['explicit_content']==1 else False,
            artist_id = track_data['primary_artists_id'], # optional
            animated_cover_url = '', # optional
            description = '', # optional
            bit_depth = 16, # optional
            sample_rate = 44.1, # optional
            bitrate = self.quality_parse[quality_tier].split('_')[-1], # optional
            download_extra_kwargs = {'file_url': self.getCdnURL(track_data['encrypted_media_url'], quality_tier), 'codec': 'AAC'}, # optional only if download_type isn't DownloadEnum.TEMP_FILE_PATH, whatever you want
            cover_extra_kwargs = {'data': {track_id: track_data}}, # optional, whatever you want, but be very careful
            credits_extra_kwargs = {'data': {track_id: track_data}}, # optional, whatever you want, but be very careful
            lyrics_extra_kwargs = {'data': {track_id: track_data}}, # optional, whatever you want, but be very careful
            error = '' # only use if there is an error
        )
    

    def getCdnURL(self, encurl: str, quality_tier):
        params = {
            '__call': 'song.generateAuthToken',
            'url': encurl,
            'bitrate': self.quality_parse[quality_tier].split('_')[-1],
            'api_version': '4',
            '_format': 'json',
            'ctx': 'web6dot0',
            '_marker': '0',
        }
        response = self.session.get('https://www.jiosaavn.com/api.php', params=params)
        return response.json()["auth_url"]

    def get_track_download(self, file_url, codec):
        track_location = create_temp_filename()
        
        # Do magic here
        return TrackDownloadInfo(
            download_type = DownloadEnum.URL,
            file_url = file_url, # optional only if download_type isn't DownloadEnum.URL
            file_url_headers = {}, # optional
            temp_file_path = track_location
        )


    def get_track_credits(self, track_id: str, data={}): # Mandatory if ModuleModes.credits
        track_data = data[track_id] if data and track_id in data else self.get_track_json(track_id)
        # print("get_track_credits", track_data)
        starring = track_data['starring'].split(', ')
        credits_dict = {
            'Starring': starring
        }
        return [CreditsInfo(k, v) for k, v in credits_dict.items()]
    
    def get_track_cover(self, track_id: str, cover_options: CoverOptions, data={}) -> CoverInfo: # Mandatory if ModuleModes.covers
        track_data = data[track_id] if data and track_id in data else self.get_track_json(track_id)
        cover_url = track_data['image'].replace('150', '500')
        return CoverInfo(url=cover_url, file_type=ImageFileTypeEnum.jpg)

    def get_track_lyrics(self, track_id: str, data={}) -> LyricsInfo: # Mandatory if ModuleModes.lyrics
        track_data = data[track_id] if data and track_id in data else self.get_track_json(track_id)
        lyric_json = self.session.get(self.lyrics_api + track_data['id']).json()
        plain_lyrics =  lyric_json.get("lyrics")
        if plain_lyrics is not None:
            plain_lyrics = plain_lyrics.replace('<br>', '\n')
            plain_lyrics = cleanhtml(plain_lyrics)
        return LyricsInfo(embedded=plain_lyrics, synced='') # both optional if not found

    def get_artist_info(self, artist_id: str, get_credited_albums: bool) -> ArtistInfo: # Mandatory if ModuleModes.download
        # get_credited_albums means stuff like remix compilations the artist was part of
        artist_data = self.session.get_artist(artist_id)

        return ArtistInfo(
            name = '',
            albums = [], # optional
            album_extra_kwargs = {'data': ''}, # optional, whatever you want
            tracks = [], # optional
            track_extra_kwargs = {'data': ''} # optional, whatever you want
        )
    
    def search_json(self, query_type, query, limit):
        qt = {
            DownloadTypeEnum.track: 'search.getResults',
            DownloadTypeEnum.playlist: 'search.getPlaylistResults',
            DownloadTypeEnum.album: 'search.getAlbumResults',
            DownloadTypeEnum.artist: 'search.getArtistResults'
        }
        params = {
            'p': '1',
            'q': query,
            '_format': 'json',
            '_marker': '0',
            'api_version': '4',
            'ctx': 'web6dot0',
            'n': str(limit),
            '__call': qt[query_type],
        }
        search_response = self.session.get('https://www.jiosaavn.com/api.php', params=params).json()
        return search_response['results']
    

    def search(self, query_type: DownloadTypeEnum, query: str, track_info: TrackInfo = None, limit: int = 10): # Mandatory
        results = {}
        print("Jiosaavn doesn't support ISRC, therefore using search query")
        results = self.search_json(query_type, query, limit)

        if query_type in [DownloadTypeEnum.track, DownloadTypeEnum.album]:
            return [SearchResult(
                    result_id = self.album_song_rx.search(i['perma_url']).group(2),
                    name = i['title'], # optional only if a lyrics/covers only module
                    artists = i['subtitle'].split(', '), # optional only if a lyrics/covers only module or an artist search
                    year = i['year'], # optional
                    explicit = True if i['explicit_content']=='1' else False, # optional
                ) for i in results]
        elif query_type == [DownloadTypeEnum.playlist, DownloadTypeEnum.artist]:
            return [SearchResult(
                    result_id = i['perma_url'].split('/')[-1],
                    name = i['title'], # optional only if a lyrics/covers only module
                ) for i in results]

