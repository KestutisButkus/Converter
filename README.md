# Vaizdo konverteris (Video Converter)

Galinga ir efektyvi vaizdo failų konvertavimo programa, optimizuota masiniam ir vienetiniam vaizdo srautų apdorojimui, naudojant techninės įrangos spartinimą (NVIDIA NVENC/NVDEC, AMD AMF).

![Programos langas](img.png)

## Funkcijos

- **Aparatinis spartinimas:** Pilnas `NVIDIA` (NVENC/NVDEC via CUDA) ir `AMD` (AMF via D3D11VA/DXVA2) palaikymas. Vaizdo išpakavimas, filtravimas ir kodavimas vyksta tiesiogiai vaizdo plokštės VRAM atmintyje.
- **Išmanusis mastelio keitimas:** Automatinis perjungimas tarp programinio `scale` ir aparatinio `scale_cuda` filtro, išlaikant maksimalų FPS.
- **Main 10 (10-bit HEVC) konversija:** Sklandus 10-bit HEVC šaltinių konvertavimas į itin suderinamą 8-bit H.264 (`yuv420p`) formatą tiesiogiai GPU viduje.
- **Lankstus kokybės valdymas:** Palaiko fiksuotos kokybės (CRF/CQ) ir tikslinio bitų srauto (VBR su automatiniu `1:4` maxrate piko saugikliu) režimus.
- **Audio apdorojimas:** Automatinis garso takelių aptikimas ir konvertavimas į suderinamą AAC formatą (96k / 128k / 192k) arba tiesioginė srauto kopija.

## Architektūra

Projektas išskaidytas į vientos atsakomybės modulius:

| Failas | Paskirtis |
|---|---|
| `converter.py` | Tkinter GUI ir konvertavimo srauto valdymas |
| `ffmpeg_engine.py` | Deterministinis FFmpeg komandų generavimas ir filtrų grandinių valdymas |
| `hardware.py` | Sistemos resursų, enkoderių ir aparatinių spartintuvų aptikimas |
| `batch_processor.py` | FFmpeg proceso valdymas, progreso skaitymas, atšaukimas |
| `app_utils.py` | Pagalbinės funkcijos: katalogų skenavimas, ETA skaičiavimas, konversijos ataskaita |
| `gui_components.py` | Bendriniai Tkinter komponentai ir stilių konstantos |
| `about.py` | „Apie programą" dialogo langas |
| `error_window.py` | Kritinės klaidos dialogo langas (pvz., nerastas FFmpeg) |

## Paleidimas iš kodo

### Reikalavimai

- Python 3.10+
- `ffmpeg` ir `ffprobe` vykdomieji failai turi būti sisteminiame PATH arba tame pačiame aplanke šalia kodo

### Įdiegimas

```bash
# Klonuoti repozitoriją
git clone https://github.com/vartotojas/video-converter.git
cd video-converter

# Įdiegti priklausomybes (standartinė biblioteka, papildomų paketų nereikia)
python -m pip install --upgrade pip
```

### Paleidimas

```bash
python converter.py
```

## FFmpeg diegimas

Jei `ffmpeg` nerastas, programa parodys instrukciją. Rankinis būdas:

1. Atsisiųskite iš [gyan.dev/ffmpeg/builds](https://www.gyan.dev/ffmpeg/builds/) — rekomenduojama `ffmpeg-release-full-shared.7z`
2. Išpakuokite ir atidarykite `bin` aplanką
3. Nukopijuokite **visus** failus tiesiai šalia `converter.exe` (arba `converter.py`):

```
ffmpeg.exe
ffprobe.exe
avcodec-*.dll
avdevice-*.dll
avfilter-*.dll
avformat-*.dll
avutil-*.dll
swresample-*.dll
swscale-*.dll
```

## Palaikoma aparatinė įranga

| Gamintojas | Dekodavimas | Kodavimas | Testavimas |
|---|---|---|---|
| NVIDIA | NVDEC (CUDA) | NVENC | GTX 1650 ✓ |
| AMD | D3D11VA / DXVA2 | AMF | — |
| CPU (atsarginis) | — | libx264 / libx265 | ✓ |

## Licencija

Copyright © 2026 Kęstutis Butkus