# Adding New Instruments (SoundFonts)

Studio P4 uses the **FluidSynth** engine, which means it relies on standard `.sf2` SoundFont files to generate audio. Expanding the studio's instrument library is as simple as dropping new files into the correct folder. 

Because the application scans this folder every time it launches, your new instruments will be automatically detected and categorized!

## 1. Locating the `sf2/` Directory

Where you place your SoundFonts depends on how you are running the application:

* **If you are running the Python source code:** Place your `.sf2` files inside the `sf2/` directory located at the root of the project folder.
* **If you are using the Standalone Executable (`.exe`):** To make customizing easy, the instrument library is kept *outside* the application. Simply ensure there is a folder named `sf2/` in the exact same location as your executable file, and drop your new instruments inside it.

*Important: The application expects an existing `metronome.sf2` file for the click track and a default piano file, like `Default/basic_piano.sf2`, in order to boot properly.*

## 2. Grouping Instruments (Folders)

When a musician uses the joystick in **Group Mode**, they are actually navigating the subfolders inside the `sf2/` directory. The application automatically reads the folder names and creates categories!

To organize your new instruments:

1. Inside the `sf2/` directory, create a new folder (e.g., `Synths`, `Bass`, `Kits`).
2. Place your downloaded `.sf2` files into these subfolders. 

**Example Structure for the Executable Version:**
```text
Studio_Folder/
├── main.exe                  (The standalone application)
└── sf2/                      (The external sound library)
    ├── basic_piano.sf2       (Will appear in the "Général" group)
    ├── Metronom.sf2
    ├── Bass/                 (Creates a "Bass" group)
    │   ├── fretless.sf2
    │   └── synth_bass.sf2
    └── Strings/              (Creates a "Strings" group)
        └── violin.sf2
```
When the app launches, the Voice Assistant will now read "Bass" and "Strings" as available instrument groups.

## 3. Where to Find Free SoundFonts

If you are looking to expand your library, here are excellent resources for open-source and free `.sf2` files:

- [Zanderjaz Free Soundfont Downloads](https://www.zanderjaz.com/downloads/soundfonts/)
- [Polyphone Soundfont Repository](https://www.polyphone.io/en/soundfonts)