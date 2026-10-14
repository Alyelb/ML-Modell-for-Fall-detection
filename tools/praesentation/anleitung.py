"""Presentation 3 (English): from a Keras model to a microcontroller.

General guide for any small Keras model; the last slides show how it is
done in this project (fall detection in a shoe insole).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from thm_deck import DUNKEL, GRAU, GRUEN, HELL, REPO, WEISS, Deck  # noqa: E402
from pptx.dml.color import RGBColor  # noqa: E402
from pptx.enum.text import PP_ALIGN  # noqa: E402

d = Deck()
T, N = d.text, d.notiz
CODE_BG = RGBColor(0x26, 0x32, 0x38)
KOMMENTAR = RGBColor(0x9C, 0xCC, 0x65)
STEPS = 6


def code(slide, x, y, w, zeilen, size=13, h=None):
    """Dark box with code; text after '#' or '//' is green."""
    h = h or 0.22 + 0.27 * len(zeilen) * size / 13
    d.flaeche(slide, x, y, w, h, fill=CODE_BG)
    absaetze = []
    for z in zeilen:
        teil = None
        for marke in ("  # ", "  // "):
            if marke in z:
                i = z.index(marke)
                teil = [(z[:i], {}), (z[i:], {"color": KOMMENTAR})]
                break
        if teil is None and z.lstrip().startswith(("# ", "// ")):
            teil = [(z, {"color": KOMMENTAR})]
        absaetze.append(teil or [(z, {})])
    tb = T(slide, x + 0.2, y + 0.11, w - 0.4, h - 0.15, absaetze, size=size, color=WEISS, abstand=1)
    for p in tb.text_frame.paragraphs:
        for r in p.runs:
            r.font.name = "Courier New"
    return tb


def step(slide, nr):
    T(slide, 10.75, 1.25, 2.0, 0.4, f"Step {nr} of {STEPS}", size=13, color=GRAU, align=PP_ALIGN.RIGHT)


def box(slide, x, y, w, h, head, lines, size=15):
    d.flaeche(slide, x, y, w, h, fill=HELL)
    T(slide, x + 0.25, y + 0.18, w - 0.5, 0.4, [[(head, {"bold": True, "color": GRAU})]], size=size)
    T(slide, x + 0.25, y + 0.65, w - 0.5, h - 0.8, lines, size=size, punkte=True, abstand=6)


B = {"bold": True}

# 1 ------------------------------------------------------------------ Title
s = d.titelfolie([
    ("From a Keras model to a microcontroller", 18, True, DUNKEL),
    ("A step-by-step guide – with the fall-detection insole as example", 12, False, GRAU),
    ("Aly Elbermawy", 12, True, DUNKEL),
    ("Study Project 2 · THM Campus Friedberg", 11, False, GRAU)])
N(s, "Starting point: a trained model saved as .keras. Goal: the same model running on a small chip.")

# 2 ------------------------------------------------------------------ Big picture
s = d.folie("The big picture")
d.ablauf(s, 0.47, 2.0, 12.3, [("1 Prepare", "model + data"), ("2 Convert", "to int8\n.tflite"),
                              ("3 Check", "on the PC"), ("4 C file", "model as\nbyte array"),
                              ("5 Firmware", "run on\nthe chip"), ("6 Test", "on the\ndevice")],
         h=1.45, hervor=(1,), size=16)
T(s, 0.47, 3.9, 12.3, 2.8, [
    [("Why convert? ", B), ("A Keras model uses 32-bit floats and needs a full computer. "
                            "A microcontroller has a few hundred KB of memory and no operating system.", {})],
    [("The idea: ", B), ("store every weight as a small integer (int8). The model becomes four times "
                         "smaller and faster – and almost as accurate.", {})],
    [("Works for any small Keras model. ", B), ("At the end I show how it is done in my project.", {})],
], size=17, punkte=True, abstand=12)
N(s, "Six steps. Steps 2 and 3 happen on the PC in Python, steps 5 and 6 on the microcontroller.")

# 3 ------------------------------------------------------------------ What you need
s = d.folie("What you need")
d.tabelle(s, 0.47, 1.95, 12.3, [
    ["What", "Why"],
    ["The trained model (model.keras)", "the network you want on the chip"],
    ["Some real input samples (e.g. 100–500)", "to choose the int8 number range and to check the result"],
    ["Python 3 with TensorFlow", "converts and checks the model"],
    ["Arduino IDE (or the vendor's toolchain)", "builds the firmware and uploads it"],
    ["A microcontroller board + USB cable", "e.g. ESP32, Arduino Nano 33 BLE, STM32"],
], [5.6, 6.7], size=16, h_zeile=0.62, zentriert_ab=2)
N(s, "The input samples must be pre-processed exactly like during training (same scaling, same window length).")

# 4 ------------------------------------------------------------------ Step 1
s = d.folie("Step 1: Prepare – load the model and the samples")
step(s, 1)
code(s, 0.47, 1.95, 7.0, [
    "pip install tensorflow numpy",
    "",
    "import numpy as np, tensorflow as tf",
    "",
    "model = tf.keras.models.load_model(\"model.keras\")",
    "model.summary()          # layers, input shape",
    "",
    "X = np.load(\"samples.npy\")  # real inputs,",
    "                           # pre-processed",
    "print(model.predict(X[:5]))  # quick sanity check",
], size=13)
box(s, 7.85, 1.95, 4.9, 3.9, "Look at", [
    "Input shape, e.g. (100, 6)",
    "Number of parameters – fits into the chip's memory?",
    "Layer types – supported on microcontrollers?"], size=15)
N(s, "Conv, Dense, Pooling, ReLU and Sigmoid work everywhere. Exotic layers (LSTM, custom layers) often do not.")

# 5 ------------------------------------------------------------------ Step 2
s = d.folie("Step 2: Convert to an int8 TensorFlow Lite model")
step(s, 2)
code(s, 0.47, 1.95, 7.6, [
    "def samples():                # real inputs",
    "    for x in X[:300]:",
    "        yield [x[None].astype(np.float32)]",
    "",
    "conv = tf.lite.TFLiteConverter.from_keras_model(model)",
    "conv.optimizations = [tf.lite.Optimize.DEFAULT]",
    "conv.representative_dataset = samples",
    "conv.target_spec.supported_ops = [",
    "    tf.lite.OpsSet.TFLITE_BUILTINS_INT8]",
    "conv.inference_input_type  = tf.int8",
    "conv.inference_output_type = tf.int8",
    "",
    "open(\"model_int8.tflite\", \"wb\").write(conv.convert())",
], size=12)
T(s, 8.4, 1.95, 4.35, 4.8, [
    [("Representative data: ", B), ("the converter looks at real inputs to decide which range of values "
                                     "is mapped to −128 … 127.", {})],
    [("Result: ", B), ("one file, model_int8.tflite, about ¼ of the original size.", {})],
], size=15, punkte=True, abstand=12)
N(s, "Without representative data the converter cannot choose good ranges and accuracy drops.")

# 6 ------------------------------------------------------------------ Step 3
s = d.folie("Step 3: Check the int8 model on the PC")
step(s, 3)
code(s, 0.47, 1.95, 7.6, [
    "it = tf.lite.Interpreter(\"model_int8.tflite\")",
    "it.allocate_tensors()",
    "inp, out = it.get_input_details()[0], it.get_output_details()[0]",
    "s_in, z_in = inp[\"quantization\"]",
    "s_out, z_out = out[\"quantization\"]",
    "",
    "for x in X[:200]:",
    "    xq = np.round(x / s_in + z_in).astype(np.int8)",
    "    it.set_tensor(inp[\"index\"], xq[None]); it.invoke()",
    "    y = (it.get_tensor(out[\"index\"]).astype(float) - z_out) * s_out",
    "    # compare y with model.predict(x[None])",
], size=12)
T(s, 8.4, 1.95, 4.35, 4.8, [
    [("Goal: ", B), ("the int8 model makes the same decision as the Keras model in well over 95 % of the samples.", {})],
    [("Note the numbers ", B), ("s_in, z_in, s_out, z_out – the chip needs them to convert inputs and outputs.", {})],
], size=15, punkte=True, abstand=12)
N(s, "Scale and zero point: real value = (int8 value − zero point) × scale.")

# 7 ------------------------------------------------------------------ Step 4
s = d.folie("Step 4: Turn the model into a C file")
step(s, 4)
T(s, 0.47, 1.95, 12.3, 0.4, "A microcontroller has no file system – the model is compiled into the firmware as a byte array.",
  size=16)
code(s, 0.47, 2.55, 12.3, ["xxd -i model_int8.tflite > model_data.h        # Linux / macOS"], size=14)
code(s, 0.47, 3.3, 12.3, [
    "# Windows: the same with Python",
    "data = open(\"model_int8.tflite\", \"rb\").read()",
    "with open(\"model_data.h\", \"w\") as f:",
    "    f.write(\"alignas(16) const unsigned char model_data[] = {\")",
    "    f.write(\",\".join(str(b) for b in data) + \"};\\n\")",
    "    f.write(f\"const unsigned int model_data_len = {len(data)};\\n\")",
], size=13)
T(s, 0.47, 5.55, 12.3, 1.0, [[("Copy model_data.h ", B), ("into the firmware folder, next to the .ino file.", {})]], size=16)
N(s, "alignas(16) is important: TFLite Micro expects the model to start on a 16-byte boundary.")

# 8 ------------------------------------------------------------------ Step 5
s = d.folie("Step 5: Run the model on the microcontroller")
step(s, 5)
code(s, 0.47, 1.95, 7.9, [
    "#include \"model_data.h\"   // + TFLite Micro headers",
    "alignas(16) uint8_t arena[40 * 1024];   // working memory",
    "",
    "auto *m = tflite::GetModel(model_data);",
    "static tflite::MicroMutableOpResolver<8> ops;",
    "ops.AddConv2D(); ops.AddFullyConnected(); // ...",
    "static tflite::MicroInterpreter it(m, ops, arena, sizeof(arena));",
    "it.AllocateTensors();",
    "",
    "TfLiteTensor *in = it.input(0), *out = it.output(0);",
    "for (int i = 0; i < N; i++)        // float -> int8",
    "  in->data.int8[i] = round(x[i] / s_in + z_in);",
    "it.Invoke();",
    "float y = (out->data.int8[0] - z_out) * s_out;",
], size=11)
T(s, 8.7, 1.95, 4.05, 4.8, [
    [("Library: ", B), ("TensorFlow Lite Micro – in the Arduino IDE via the library manager for your board.", {})],
    [("Arena: ", B), ("memory for intermediate results; start large, then reduce.", {})],
    [("Resolver: ", B), ("register exactly the operations your model uses.", {})],
], size=15, punkte=True, abstand=12)
N(s, "The input must be pre-processed on the chip exactly as in training – same sampling rate, window, scaling.")

# 9 ------------------------------------------------------------------ Step 6
s = d.folie("Step 6: Test on the device")
step(s, 6)
d.ablauf(s, 0.47, 1.95, 12.3, [("Known input", "same sample\nas on the PC"), ("Same output?", "compare with\nstep 3"),
                              ("Live data", "real sensor"), ("Plausible?", "watch the output\nwhile testing")],
         h=1.35, hervor=(1,), size=16)
T(s, 0.47, 3.65, 12.3, 3.0, [
    [("First a self-test: ", B), ("put a few fixed inputs into the firmware whose output you computed on the PC. "
                                  "If the chip gives a different result, every later number is wrong.", {})],
    [("Then live: ", B), ("print every output over the serial monitor and do the real movements.", {})],
    [("Measure the time ", B), ("for one inference – it must be shorter than the time between two decisions.", {})],
], size=16, punkte=True, abstand=10)
N(s, "The self-test is the most important lesson of my project – see the last slides.")

# 10 ------------------------------------------------------------------ Problems
s = d.folie("Common problems")
d.tabelle(s, 0.47, 1.95, 12.3, [
    ["What you see", "Likely cause", "What helps"],
    ["Wrong results on the chip", "different pre-processing than in training", "use identical scaling, window, rate"],
    ["AllocateTensors fails", "arena too small", "make the arena larger"],
    ["“Didn't find op …”", "operation not registered", "add it to the resolver"],
    ["Same output for every input", "input not converted, or a library bug", "check scale/zero point; self-test"],
    ["Model does not fit", "too many parameters", "smaller network, int8"],
], [3.9, 4.3, 4.1], size=15, h_zeile=0.6, zentriert_ab=3)
N(s, "The fourth row is exactly what happened in my project.")

# 11 ------------------------------------------------------------------ Glossary
s = d.folie("Terms in one sentence")
d.tabelle(s, 0.47, 1.95, 12.3, [
    ["Term", "Meaning"],
    ["TensorFlow / Keras", "library for training neural networks; Keras builds the network from layers"],
    [".keras", "the trained model with 32-bit floats"],
    ["TensorFlow Lite (.tflite)", "compact file format for small devices"],
    ["int8 / quantisation", "every weight stored as an integer from −128 to 127"],
    ["TensorFlow Lite Micro", "library that runs .tflite models on microcontrollers"],
    ["Kernel", "small function that computes one layer type (convolution, dense, …)"],
], [3.6, 8.7], size=15, h_zeile=0.58, zentriert_ab=2)
N(s, "For reference.")

# 12 ------------------------------------------------------------------ My case: overview
s = d.folie("My case: fall detection in a shoe insole")
d.tabelle(s, 0.47, 1.95, 12.3, [
    ["Generic step", "In my project"],
    ["model.keras", "fall_model_lowerlimb_aug.keras (1D-CNN, 61 601 weights)"],
    ["Input samples", "Pilotdaten/ – own recordings (CSV) from the DatenLogger firmware"],
    ["Steps 2–4", "one script: tools/export_firmware_model.py"],
    ["Firmware folder", "firmware/CleverSole/ (CleverSole.ino)"],
    ["Board", "Seeed XIAO ESP32-C6 + MPU-6500, 100 Hz, ±16 g"],
    ["Input", "2 s × 6 channels (acceleration + rotation), 50 Hz → 100 × 6"],
], [3.2, 9.1], size=15, h_zeile=0.6, zentriert_ab=2)
N(s, "Same six steps – only the names are specific.")

# 13 ------------------------------------------------------------------ My case: export
s = d.folie("My case: one command does steps 2 to 4")
code(s, 0.47, 1.95, 12.3, ["python tools/export_firmware_model.py fall_model_lowerlimb_aug.keras Pilotdaten/"], size=15)
d.tabelle(s, 0.47, 2.8, 12.3, [
    ["Output file", "Where", "Content"],
    ["fall_model_lowerlimb_aug_int8.tflite", "next to the .keras file", "the int8 model (archive)"],
    ["modell_netz.h", "firmware/CleverSole/", "weights as C arrays – used by the chip"],
    ["modell_sohle.h", "firmware/CleverSole/", "model bytes + self-test values"],
], [4.6, 3.4, 4.3], size=14, h_zeile=0.5, hervor=(2,), zentriert_ab=3)
T(s, 0.47, 4.95, 12.3, 1.8, [
    [("Special: ", B), ("TFLite Micro gave the same output (0.47) for every input on the ESP32-C6. "
                        "So the firmware uses its own int8 kernels (netz_int8.h, ~130 lines of C) with the same "
                        "weights. The script checks them on the PC against TensorFlow Lite: same decisions.", {})],
], size=15)
N(s, "BatchNorm layers are folded into the following layer automatically. The .tflite file itself is not executed on the chip.")

# 14 ------------------------------------------------------------------ My case: upload and test
s = d.folie("My case: upload and watch it live")
T(s, 0.47, 1.95, 5.9, 4.8, [
    [("Open ", B), ("firmware/CleverSole/CleverSole.ino in the Arduino IDE, board “ESP32C6 Dev Module”, upload.", {})],
    [("Serial monitor, 115200: ", B), ("five self-tests must say OK.", {})],
    [("Stand 1 s, walk 10–15 steps: ", B), ("the chip calibrates its mounting, then the model runs.", {})],
    [("Every 0.2 s ", B), ("one LIVE line – also on the phone via the app “Serial Bluetooth Terminal”.", {})],
], size=15, punkte=True, abstand=10)
code(s, 6.6, 1.95, 6.15, [
    "Selbsttest 0..4: ... OK",
    "Modell (eigene Kerne) ok",
    "12 Schritte, ... -> Inferenz aktiv",
    "",
    "LIVE Sturz  2% [..........] 0/5 kein Sturz",
    "LIVE Sturz 91% [#########.] 1/5 Verdacht",
    "LIVE Sturz 97% [##########] 3/5 STURZ!",
], size=11)
T(s, 6.6, 4.35, 6.15, 2.3, [
    [("Sturz %: ", B), ("network output for the last 2 s", {})],
    [("3/5: ", B), ("windows above 50 % among the last five", {})],
    [("STURZ!: ", B), ("alarm, exactly one per fall (≈ 117 ms per inference)", {})],
], size=14, punkte=True, abstand=6)
N(s, "The serial output is in German because the firmware is. Details: firmware/CleverSole/ANLEITUNG.md.")

# 15 ------------------------------------------------------------------ Questions
s = d.folie("Questions?")
T(s, 0.47, 2.3, 12.3, 2.0, [
    "Code, notebooks and firmware:",
    [("github.com/Alyelb/ML-Modell-for-Fall-detection", B)],
], size=20, color=GRAU, abstand=10)
N(s, "Thank you.")

d.speichern(REPO / "praesentation" / "3_Anleitung_Modell_auf_den_Chip.pptx")
