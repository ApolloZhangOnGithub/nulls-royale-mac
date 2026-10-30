import importlib.util
from pathlib import Path
import struct
import tempfile
import unittest
import zipfile

spec = importlib.util.spec_from_file_location('converter', Path(__file__).resolve().parents[1] / 'convert.py')
converter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(converter)


def binary(first_section=512):
    data = bytearray(first_section + 4)
    struct.pack_into('<8I', data, 0, 0xfeedfacf, 0x100000c, 0, 2, 1, 152, 0, 0)
    struct.pack_into('<II16sQQQQIIII', data, 32, 0x19, 152, b'__TEXT',
                     0x100000000, 4096, 0, len(data), 5, 5, 1, 0)
    struct.pack_into('<16s16sQQIIIIIIII', data, 104, b'__text', b'__TEXT',
                     0x100000000 + first_section, 4, first_section, 2, 0, 0, 0, 0, 0, 0)
    data[first_section:] = bytes.fromhex('c0035fd6')
    return data


class ConversionSafetyTests(unittest.TestCase):
    def test_injection_preserves_code_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'game'
            path.write_bytes(binary())
            before = converter.sections(path.read_bytes())
            converter.inject(path, '@executable_path/Frameworks/test.dylib')
            once = path.read_bytes()
            self.assertEqual(before, converter.sections(once))
            self.assertEqual(struct.unpack_from('<I', once, 16)[0], 2)
            converter.inject(path, '@executable_path/Frameworks/test.dylib')
            self.assertEqual(once, path.read_bytes())

    def test_rejects_header_overflow_without_modifying_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'game'
            before = binary(184)
            path.write_bytes(before)
            with self.assertRaises(ValueError):
                converter.inject(path, '@executable_path/Frameworks/test.dylib')
            self.assertEqual(before, path.read_bytes())

    def test_section_fingerprint_detects_code_mutation(self):
        before = binary()
        after = bytearray(before)
        after[-1] ^= 1
        self.assertNotEqual(converter.sections(before), converter.sections(after))

    def test_rejects_zip_traversal_before_extracting(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            output = root / 'output'
            output.mkdir()
            archive = root / 'input.ipa'
            with zipfile.ZipFile(archive, 'w') as z:
                z.writestr('Payload/Test.app/Info.plist', b'placeholder')
                z.writestr('../escape', b'bad')
            with self.assertRaises(ValueError):
                converter.extract(archive, output)
            self.assertEqual(list(output.iterdir()), [])
            self.assertFalse((root / 'escape').exists())


if __name__ == '__main__':
    unittest.main()
