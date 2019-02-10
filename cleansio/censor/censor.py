""" Censors audio chunks by muting explicit sections """

from multiprocessing import Lock
from pydub import AudioSegment
from speech import Timestamp, Transcribe

class Censor():
    """ Superclass of CensorFile and CensorRealtime """
    lock = Lock()
    explicit_count = 0
    muted_timestamps = []

    def __init__(self, explicits):
        super().__init__()
        self.explicits = explicits

    def censor_audio_chunk(self, file_path):
        """ Common process to censor an audio chunk """
        chunk = AudioSegment.from_file(file_path)
        lyrics = self.__get_lyrics(file_path, chunk)
        timestamps = self.__get_timestamps(lyrics)
        if timestamps:
            self.__mute_explicits(file_path, chunk, timestamps)
        # Return a new AudioSegment object because the file may have changed
        return AudioSegment.from_file(file_path)

    def __mute_explicits(self, file_path, chunk, timestamps):
        """ Go through each word, if its an explicit, mute the duration """
        muted = False
        for stamp in timestamps:
            if stamp['word'] in self.explicits: # Explicit found, mute
                audio_segment = self.__mute_explicit(audio_segment, stamp)
                muted = True
                chunk_index = int(file_path.split('-')[-1].split('.')[0])
                self.__explicit_count(stamp, chunk_index * 5000)
        if muted:
            Censor.lock.acquire()
            # Overwrite the chunk with the mute(s) safely
            audio_segment.export(file_path, format='wav')
            Censor.lock.release()

    @classmethod
    def __mute_explicit(cls, chunk, timestamp):
        len_as = len(chunk)
        # Check if the timestamp is outside of this chunk (from overlapping)
        if timestamp['start'] > len_as:
            return chunk
        beginning = chunk[:timestamp['start']]
        duration = timestamp['end'] - timestamp['start']
        mute = AudioSegment.silent(duration=duration)
        # The end of the timestamp cannot be longer than the file
        end_length = len_as if len_as < timestamp['end'] else timestamp['end']
        end = chunk[end_length:]
        return beginning + mute + end

    @classmethod
    def __get_lyrics(cls, file_path, chunk):
        return Transcribe(file_path, chunk.frame_rate).lyrics

    @classmethod
    def __get_timestamps(cls, lyrics):
        return Timestamp(lyrics).timestamps

    @classmethod
    def __explicit_count(cls, stamp, chunk_offset):
        """ Count the number of explicits safely """
        stamp['start'] += chunk_offset
        stamp['end'] += chunk_offset
        new_stamp = True
        Censor.lock.acquire()
        for mut in Censor.muted_timestamps:
            if cls.__duplicate_stamp(mut, stamp):
                new_stamp = False
                break
        if new_stamp or not Censor.muted_timestamps:
            Censor.explicit_count += 1
            Censor.muted_timestamps.append(stamp)
        Censor.lock.release()

    @classmethod
    def __duplicate_stamp(cls, stamp1, stamp2):
        """ If 2 timestamps are the same word and start and at relatively the
            same time, then assume they're the same timestamp """
        if stamp1['word'] == stamp2['word'] and            \
          abs(stamp1['start'] - stamp2['start']) < 201 and \
          abs(stamp1['end'] - stamp2['end']) < 201:
            return True
        return False
