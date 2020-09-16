import torchaudio
from fastai.data.external import URLs
from fastai.data.transforms import Transform, get_files
from fastai.imports import Path, mimetypes, plt, tarfile
from fastai.torch_core import TensorBase
from fastai.vision.data import get_grid
from fastcore.dispatch import retain_type, typedispatch
from fastai.basics import delegates
from fastcore.utils import add_props, ifnone
from IPython.display import Audio, display
from librosa.display import waveplot

audio_extensions = tuple(
    str.lower(k) for k, v in mimetypes.types_map.items() if v.startswith("audio/")
)


def get_audio_files(path, recurse=True, folders=None):
    "Get audio files in `path` recursively, only in `folders`, if specified."
    return get_files(
        path, extensions=audio_extensions, recurse=recurse, folders=folders
    )


def AudioGetter(suf="", recurse=True, folders=None):
    """Create `get_audio_files` partial function that searches path suffix `suf`
    and passes along `kwargs`, only in `folders`, if specified."""

    def _inner(o, recurse=recurse, folders=folders):
        return get_audio_files(o / suf, recurse, folders)

    return _inner


URLs.SPEAKERS10 = "http://www.openslr.org/resources/45/ST-AEDS-20180100_1-OS.tgz"
URLs.ESC50 = "https://github.com/karoldvl/ESC-50/archive/master.zip"
URLs.SAMPLE_SPEAKERS10 = (
    "https://github.com/fastaudio/10_Speakers_Sample/archive/master.zip"
)


def tar_extract_at_filename(fname, dest):
    "Extract `fname` to `dest`/`fname.name` folder using `tarfile`"
    dest = Path(dest) / Path(fname).with_suffix("").name
    tarfile.open(fname, "r:gz").extractall(dest)


class AudioTensor(TensorBase):
    """
    Semantic torch tensor that represents an audio.
    Contains all of the functionality of a normal tensor,
    but additionally can be created from files and has
    extra properties. Also knows how to show itself.
    """

    @classmethod
    @delegates(torchaudio.load, keep=True)
    def create(cls, fn, cache_folder=None, **kwargs):
        "Creates audio tensor from file"
        if cache_folder is not None:
            fn = cache_folder / fn.name
        sig, sr = torchaudio.load(fn, **kwargs)
        return cls(sig, sr=sr)

    @property
    def sr(self):
        "Property. Sampling rate of the audio"
        return self.get_meta("sr")

    def __new__(cls, x, sr=None, **kwargs):
        return super().__new__(cls, x, sr=sr, **kwargs)

    # This one should probably use set_meta() but there is no documentation,
    # and I could not get it to work. Even TensorBase.set_meta?? is pointing
    # to the wrong source because of fastai patch on Tensorbase to retain types
    @sr.setter
    def sr(self, val):
        self._meta["sr"] = val

    nsamples, nchannels = add_props(lambda i, self: self.shape[-1 * (i + 1)])

    @property
    def duration(self):
        return self.nsamples / float(self.sr)

    def hear(self):
        "Listen to audio clip. Creates a html player."
        display(Audio(self.cpu(), rate=self.sr))

    def show(self, ctx=None, hear=True, **kwargs):
        """Show audio clip using librosa.
        Pass `hear=True` to also display a html
        player to listen.
        """
        if hear:
            self.hear()
        return show_audio_signal(self, ctx=ctx, **kwargs)


def _get_f(fn):
    def _f(self, *args, **kwargs):
        res = getattr(super(TensorBase, self), fn)(*args, **kwargs)
        return retain_type(res, self)

    return _f


setattr(AudioTensor, "__getitem__", _get_f("__getitem__"))


def show_audio_signal(ai, ctx, ax=None, title="", **kwargs):
    ax = ifnone(ax, ctx)
    if ax is None:
        _, ax = plt.subplots()
    ax.axis(False)
    for i, channel in enumerate(ai):
        # x_start, y_start, x_lenght, y_lenght, all in percent
        ia = ax.inset_axes((i / ai.nchannels, 0.2, 1 / ai.nchannels, 0.7))
        waveplot(channel.cpu().numpy(), ai.sr, ax=ia, **kwargs)
        ia.set_title(f"Channel {i}")
    ax.set_title(title)

    return ax


@typedispatch
def show_batch(
    x: AudioTensor,
    y,
    samples,
    ctxs=None,
    max_n=6,
    nrows=2,
    ncols=1,
    figsize=None,
    **kwargs,
):
    if figsize is None:
        figsize = (4 * x.nchannels, 6)

    if ctxs is None:
        ctxs = get_grid(
            min(len(samples), max_n), nrows=nrows, ncols=ncols, figsize=figsize
        )
    ctxs = show_batch[object](
        x, y, samples, ctxs=ctxs, max_n=max_n, hear=False, **kwargs
    )
    return ctxs


class OpenAudio(Transform):
    """
    Transform that creates AudioTensors from a list of files.
    """

    def __init__(self, items):
        self.items = items

    def encodes(self, i):
        o = self.items[i]
        return AudioTensor.create(o)

    def decodes(self, i) -> Path:
        return self.items[i]
