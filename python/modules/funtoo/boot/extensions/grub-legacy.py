# -*- coding: ascii -*-

import os
import shlex

from subprocess import Popen
from subprocess import PIPE
from subprocess import STDOUT

from funtoo.boot.extension import Extension

def getExtension(config):
	return GRUBLegacyExtension(config)

class GRUBLegacyExtension(Extension):

	def __init__(self,config):
		Extension.__init__(self,config)
		self.fn = "{path}/{dir}/{file}".format(path = self.config["boot/path"], dir = self.config["grub-legacy/dir"], file = self.config["grub-legacy/file"])
		self.bootitems = []

	def isAvailable(self):
		msgs=[]
		ok=True
		return [ok, msgs]

	def generateOtherBootEntry(self,l,sect):
		ok=True
		msgs=[]
		mytype = self.config["{s}/type".format(s = sect)].lower()
		if mytype in ["dos", "msdos"]:
			mytype = "dos"
		elif mytype in ["windows", "windows 2000", "win2000", "windows xp", "winxp"]:
			mytype = "winxp"
		elif mytype in ["windows vista", "vista"]:
			mytype = "vista"
		elif mytype in ["windows 7", "win7"]:
			mytype = "win7"
		else:
			ok = False
			msgs.append(["fatal","Unrecognized boot entry type \"{type}\"".format(type = mytype)])
			return [ ok, msgs ]
		params=self.config["{s}/params".format(s = sect)].split()
		myroot = self.r.GetParam(params,"root=")
		# TODO check for valid root entry
		l.append("title {s}".format(s = sect))
		#self.PrepareGRUBForDevice(myroot,l)
		self.bootitems.append(sect)
		mygrubroot = self.DeviceGRUB(myroot)
		if mygrubroot == None:
			msgs.append(["fatal","Couldn't determine root device using grub-probe"])
			return [ False, msgs ]
		l.append("root {dev}".format(dev = mygrubroot))
		if mytype == "win7":
			l.append("chainloader +4")
		elif mytype in [ "vista", "dos", "winxp" ]:
			l.append("chainloader +1")
		l.append("")
		return [ ok, msgs ]

	def DeviceOfFilesystem(self,fs):
		return self.Guppy(" --target=device {f}".format(f = fs))

	def Guppy(self,argstring,fatal=True):
		# gmkdevmap and grub-probe is from grub-1.97+ -- we use it here as well
		if not os.path.exists("{path}/{dir}/device.map".format(path = self.config["boot/path"], dir = self.config["grub/dir"])):
			gmkdevmap = self.config["grub/grub-mkdevicemap"]
			cmdobj = Popen([gmkdevmap, "--no-floppy"], bufsize = -1, stdout = PIPE, stderr = STDOUT, shell = False)
			if cmdobj.poll() != 0:
				output = cmdobj.communicate()
				print("ERROR calling {cmd}, Output was:\n{out}".format(cmd = gmkdevmap, out = output[0]))
				return None

		gprobe = self.config["grub/grub-probe"]
		cmd = shlex.split("{gcmd} {args}".format(gcmd = gprobe, args = argstring))
		cmdobj = Popen(cmd, bufsize = -1, stdout = PIPE, stderr = STDOUT, shell = False)
		output = cmdobj.communicate()
		if cmdobj.poll() != 0:
			print("ERROR calling {cmd} {args}, Output was:\n{out}".format(cmd = gprobe, args = argstring, out = output[0]))
			return None
		else:
			return output[0].strip("\n")

	def DeviceGRUB(self,dev):
		out=self.Guppy(" --device {d} --target=drive".format(d = dev))
		# Convert GRUB "count from 1" (hdx,y) format to legacy "count from 0" format
		if out == None:
			return None
		mys = out[1:-1].split(",")
		mys = ( mys[0], repr(int(mys[1]) - 1) )
		out = "({d},{p})".format(d = mys[0], p = mys[1])
		return out

	def generateBootEntry(self,l,sect,kname,kext):

		ok=True
		allmsgs=[]

		label = self.r.GetBootEntryString( sect, kname )

		l.append("title {name}".format(name = label))
		self.bootitems.append(label)

		kpath=self.r.RelativePathTo(kname,"/boot")
		params=self.config.item(sect,"params").split()

		ok, allmsgs, myroot = self.r.DoRootAuto(params,ok,allmsgs)
		if not ok:
			return [ ok, allmsgs ]
		ok, allmsgs, fstype = self.r.DoRootfstypeAuto(params,ok,allmsgs)
		if not ok:
			return [ ok, allmsgs ]

		mygrubroot = self.DeviceGRUB(self.DeviceOfFilesystem(self.config["boot/path"]))
		if mygrubroot == None:
			allmsgs.append(["fatal","Could not determine device of filesystem using grub-probe"])
			return [ False, allmsgs ]
		# print out our grub-ified root setting
		l.append("root {dev}".format(dev = mygrubroot ))
		l.append("linux {k} {par}".format(k = kpath, par = " ".join(params)))
		initrds=self.config.item(sect,"initrd")
		initrds=self.r.FindInitrds(initrds, kname, kext)
		for initrd in initrds:
			l.append("initrd {rd}".format(rd = self.r.RelativePathTo(initrd,"/boot")))
		l.append("")

		return [ ok, allmsgs ]

	def generateConfigFile(self):
		l=[]
		ok=True
		allmsgs=[]
		# pass our boot entry generator function to GenerateSections, and everything is taken care of for our boot entries

		ok, msgs, self.defpos, self.defname = self.r.GenerateSections(l,self.generateBootEntry, self.generateOtherBootEntry)
		allmsgs += msgs
		if not ok:
			return [ ok, allmsgs, l ]

		l = [
			self.config.condFormatSubItem("boot/timeout", "timeout {s}"),
			"default {pos}".format(pos = self.defpos),
			""
		] + l

		return [ok, allmsgs, l ]

