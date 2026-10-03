"""Tests semantic pose continuity, real GPU motion and unchanged audio timing."""
import unittest,json
from pathlib import Path
import numpy as np
from render_motion import MotionRenderer,SOURCE,FPS

class MotionTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.r=MotionRenderer(SOURCE,width=540,height=960,with_overlay=False)
 @classmethod
 def tearDownClass(cls):cls.r.close()
 def test_eight_sections_and_duration(self):
  self.assertEqual(len(self.r.timeline['scenes']),8)
  self.assertEqual(round(self.r.timeline['duration']*FPS),4600)
  self.assertLess(self.r.timeline['duration'],180)
 def test_transition_pose_is_continuous(self):
  for scene in self.r.timeline['scenes'][1:]:
   t=scene['start'];a=self.r.state(t-0.0001)[2];b=self.r.state(t+0.0001)[2]
   for key in a:self.assertLess(float(np.max(np.abs(np.asarray(a[key])-np.asarray(b[key])))),.012,(scene['id'],key))
 def test_valid_finite_poses(self):
  for t in np.arange(0,153.3,.25):
   i,l,p,s=self.r.state(float(t));self.assertGreater(p['ps'],.5)
   for v in p.values():self.assertTrue(np.isfinite(np.asarray(v)).all())
 def test_real_3d_motion_in_every_scene(self):
  for scene in self.r.timeline['scenes']:
   t=scene['start']+min(5.,scene['duration']/2)
   a=np.frombuffer(self.r.frame(t),dtype=np.uint8).astype(float)
   b=np.frombuffer(self.r.frame(t+.4),dtype=np.uint8).astype(float)
   self.assertGreater(float(np.abs(a-b).mean()),.2,scene['id'])
 def test_render_is_deterministic_when_seeking(self):
  a=self.r.frame(62.0);self.r.frame(85.0);b=self.r.frame(62.0)
  self.assertEqual(a,b)

if __name__=='__main__':unittest.main(verbosity=2)
