import unittest
try:
    import av
    import numpy as np
except ImportError:av=None
from egobits.core.acoustic import AcousticMeter,RATE


@unittest.skipUnless(av,'Requires pinned audio dependencies')
class AcousticTests(unittest.TestCase):
    def measure(self,amplitude,channels=1):
        meter=AcousticMeter(channels);t=np.arange(RATE*3)/RATE
        signal=(amplitude*np.sin(2*np.pi*1000*t)).astype(np.float32)
        for start in range(0,len(t),4096):meter.feed(np.tile(signal[start:start+4096],(channels,1)))
        return meter.result()

    def test_sine_loudness_reference_and_stereo_gain(self):
        mono=self.measure(.1);stereo=self.measure(.1,2)
        self.assertAlmostEqual(mono['integrated_lufs'],-23.0,delta=.2)
        self.assertAlmostEqual(stereo['integrated_lufs']-mono['integrated_lufs'],3.0103,delta=.03)
        self.assertEqual(mono['energy_kind'],'estimated')

    def test_silence_and_level_scaling(self):
        self.assertIsNone(self.measure(0)['integrated_lufs'])
        self.assertEqual(self.measure(0)['value'],0)
        a=self.measure(.1);b=self.measure(.2)
        self.assertAlmostEqual(b['integrated_lufs']-a['integrated_lufs'],6.0206,delta=.03)
        self.assertGreater(b['value'],a['value'])
