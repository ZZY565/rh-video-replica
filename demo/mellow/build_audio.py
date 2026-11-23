# coding: utf-8
"""Recreate this concept film's original synthesized cue. Requires numpy."""
from pathlib import Path
import numpy as np,wave
R=Path(__file__).resolve().parent
sr=48000;n=15*sr;t=np.arange(n)/sr;rng=np.random.default_rng(20261123);a=np.zeros(n)
for freq,gain in [(55,.08),(110,.04),(164.814,.025),(220,.014),(261.626,.012)]:
 a+=gain*np.sin(2*np.pi*freq*t+.018*np.sin(2*np.pi*.13*t))*np.minimum(t/1.5,1)
for start,note in [(0,220),(1.2,261.626),(4.08,329.628),(6.04,293.665),(8.88,261.626),(11.4,220),(12.1,329.628)]:
 dt=t-start;env=np.exp(-np.maximum(dt,0)/1.4)*(dt>=0)
 a+=.11*env*(np.sin(2*np.pi*note*dt)+.32*np.sin(2*np.pi*note*2*dt))
 noise=rng.normal(0,1,n);sm=np.convolve(noise,np.ones(31)/31,mode='same')
 a+=.08*sm*np.exp(-np.maximum(dt,0)*12)*(dt>=0)
for start in np.arange(8.9,11.25,.065):
 dt=t-start;env=np.exp(-np.maximum(dt,0)*130)*(dt>=0);a+=.015*rng.normal(size=n)*env
fade=np.minimum(t/.5,1)*np.clip((15-t)/1.0,0,1);a*=fade;a/=max(1,np.max(np.abs(a))/.65)
stereo=np.stack([a,np.roll(a,round(sr*.007))*.97],1);stereo[-400:]*=np.linspace(1,0,400)[:,None]
with wave.open(str(R/'original-craft-cue.wav'),'wb') as w:
 w.setnchannels(2);w.setsampwidth(2);w.setframerate(sr);w.writeframes((stereo*32767).astype('<i2').tobytes())
print('15s original synthesized stereo cue saved; no source soundtrack used')
