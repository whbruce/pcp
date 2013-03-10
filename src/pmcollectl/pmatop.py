#!/usr/bin/python

#
# pmatop.py
#
# Copyright (C) 2013 Red Hat Inc.
#
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation; either version 2 of the License, or (at your
# option) any later version.
# 
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
# or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License
# for more details.
#

"""Advanced System & Process Monitor using the libpcp Wrapper module

Additional Information:

Performance Co-Pilot Web Site
http://oss.sgi.com/projects/pcp
"""

##############################################################################
#
# imports
#

import pmapi
import time
import sys
import curses
from pcp import *
from ctypes import *
from pmsubsys import cpu, interrupt, disk, memory, net, proc, subsys

me = "pmcollectl"

def usage ():
    print "\nUsage:", sys.argv[0], "\n\t[-d|-c|-n|-s|-v|-c|-y|-u|-p] [-C|-M|-D|-N|-A] [-f|--filename FILE] [-p|--playback FILE]"


# round  -----------------------------------------------------------------


def round (value, magnitude):
    return (value + (magnitude / 2)) / magnitude


# get_dimension  ---------------------------------------------------------


def get_dimension (value):
    if type(value) != type(int()) and type(value) != type(long()):
        dim = len(value)
    else:
        dim = 1
    return dim
        

# get_scalar_value  ------------------------------------------------------


def get_scalar_value (var, idx):

    if type(var) != type(int()) and type(var) != type(long()):
        return var[idx]
    else:
        return var


# record ---------------------------------------------------------------

def record (pm, config, duration, file):
    global me

    # -f saves the metrics in a directory
    if os.path.exists(file):
        print me + "playback directory %s already exists\n" % file
        sys.exit(1)
    os.mkdir (file)
    status = pm.pmRecordSetup (file + "/" + me + ".pcp", me, 0)
    check_code (status)
    (status, rhp) = pm.pmRecordAddHost ("localhost", 1, config)
    check_code (status)
    status = pm.pmRecordControl (0, pmapi.PM_REC_SETARG, "-T" + str(duration) + "sec")
    check_code (status)
    status = pm.pmRecordControl (0, pmapi.PM_REC_ON, "")
    check_code (status)
    time.sleep(duration)
    pm.pmRecordControl (0, pmapi.PM_REC_STATUS, "")
    status = pm.pmRecordControl (rhp, pmapi.PM_REC_OFF, "")
    if status < 0 and status != pmapi.PM_ERR_IPC:
        check_status (status)


# record_add_creator ------------------------------------------------------

def record_add_creator (fn):
    f = open (fn + "/" + me + ".pcp", "r+")
    args = ""
    for i in sys.argv:
        args = args + i + " "
    f.write("# Created by " + args)
    f.write("\n#\n")
    f.close()

# record_check_creator ------------------------------------------------------

def record_check_creator (fn, doc):
    f = open (fn + "/" + me + ".pcp", "r")
    line = f.readline()
    if line.find("# Created by ") == 0:
        print doc + line[13:]
    f.close()


# minutes_seconds ----------------------------------------------------------


def minutes_seconds (millis):
    dt = datetime.timedelta(0,millis/1000)
    hours = dt.days * 24
    minutes = dt.seconds / 60
    hours += minutes / 60
    minutes = minutes % 60
    return "%dh%dm" % (hours,minutes)


# _atop_print --------------------------------------------------

class _atop_print(object):
    def set_stdscr(self, a_stdscr):
        self.p_stdscr = a_stdscr
    def prc(self):
        True


# _cpu_print --------------------------------------------------


class _cpu_print(_atop_print, cpu):
    def prc(self):
        self.p_stdscr.addstr ('PRC | sys %8s | user %8s | #proc %8d | #zombie %8d\n' % (
            minutes_seconds(self.get_metric_value('kernel.all.cpu.sys')),
            minutes_seconds(self.get_metric_value('kernel.all.cpu.user')),
            self.get_metric_value('kernel.all.nprocs'), self.get_metric_value('proc.runq.defunct'))
                       )
    def cpu(self):
        self.get_total()
        self.p_stdscr.addstr ('CPU | sys %7d%% | user %7d%% | irq %7d%% | idle %7d%% | wait %7d%%\n' % (
            100 * self.get_metric_value('kernel.all.cpu.sys') / self.cpu_total,
            100 * self.get_metric_value('kernel.all.cpu.user') / self.cpu_total,
            100 * self.get_metric_value('kernel.all.cpu.irq.hard') / self.cpu_total +
            100 * self.get_metric_value('kernel.all.cpu.irq.soft') / self.cpu_total,
            100 * self.get_metric_value('kernel.all.cpu.idle') / self.cpu_total,
            100 * self.get_metric_value('kernel.all.cpu.wait.total') / self.cpu_total)
                       )
        for k in range(len(self.get_metric_value('kernel.percpu.cpu.user'))):
            self.p_stdscr.addstr ('cpu | sys %7d%% | user %7d%% | irq %7d%% | idle %7d%% | wait %7d%%\n' % (
                100 * self.get_metric_value('kernel.percpu.cpu.sys')[k] / self.cpu_total,
                100 * self.get_metric_value('kernel.percpu.cpu.user')[k] / self.cpu_total,
                100 * self.get_metric_value('kernel.percpu.cpu.irq.hard')[k] / self.cpu_total +
                100 * self.get_metric_value('kernel.percpu.cpu.irq.soft')[k] / self.cpu_total,
                100 * self.get_metric_value('kernel.percpu.cpu.idle')[k] / self.cpu_total,
                100 * self.get_metric_value('kernel.percpu.cpu.wait.total')[k] / self.cpu_total)
                           )
        self.p_stdscr.addstr ('CPL | avg1 %7.2f | avg5 %8.2f | avg15 %6.2f | csw  %5.2e | intr %5.2e\n' % (
            self.get_metric_value('kernel.all.load')[0],
            self.get_metric_value('kernel.all.load')[1],
            self.get_metric_value('kernel.all.load')[2],
            self.get_metric_value('kernel.all.pswitch'),
            self.get_metric_value('kernel.all.intr')
            )
                       )

# _interrupt_print --------------------------------------------------


class _interrupt_print(_atop_print, interrupt):
        True


# _disk_print --------------------------------------------------


class _disk_print(_atop_print, disk):
    def disk(self, pm):
        for j in xrange(len(self.metric_pmids)):
            try:
                (inst, iname) = pm.pmGetInDom(self.metric_descs [j])
                break
            except pmErr, e:
                iname = iname = "X"
        # we also want LVMs here; so we want to use disk.partition.*
        # lvm partitions have names like dm-N; but we want to get the real name
        for j in xrange(get_dimension(self.get_metric_value('disk.dev.read_bytes'))):
            self.p_stdscr.addstr ('DSK | %12s | busy %7d%% | read %7d | write %5.2g | avio %6.2f\n' % (
                iname[j],
                0, # self.get_metric_value('disk.dev.avactive')
                self.get_metric_value('disk.dev.read'),
                self.get_metric_value('disk.dev.write'),
                0
                )
                           )

# _memory_print --------------------------------------------------


class _memory_print(_atop_print, memory):
    def mem(self):
        self.p_stdscr.addstr ('MEM | tot %7dM | free %7dM | cache %5dM | buff %7dM | slab %6dM\n' % (
            round(self.get_metric_value('mem.physmem'),1000),
            round(self.get_metric_value('mem.freemem'),1000),
            round(self.get_metric_value('mem.util.cached'),1000),
            round(self.get_metric_value('mem.util.bufmem'),1000),
            round(self.get_metric_value('mem.util.slab'),1000),
            )
                       )
        self.p_stdscr.addstr ('SWP | tot %7dG | free %7dG |              | vmcom %6dG | vmlim %6dG\n' % (
            round(self.get_metric_value('mem.util.swapTotal'), 1000000),
            round(self.get_metric_value('mem.util.swapFree'), 1000000),
            round(self.get_metric_value('mem.util.committed_AS'), 1000000),
            round(self.get_metric_value('mem.util.commitLimit'), 1000000),
            )
                       )
        self.p_stdscr.addstr ('PAG | scan %7d | steal %7d | stall %6d | swin %8d | swout %5d\n' % (
            self.get_metric_value('mem.vmstat.slabs_scanned'),
            self.get_metric_value('mem.vmstat.pginodesteal'),
            self.get_metric_value('mem.vmstat.allocstall'),
            self.get_metric_value('mem.vmstat.pswpin'),
            self.get_metric_value('mem.vmstat.pswpout')
            )
                       )

# _net_print --------------------------------------------------


class _net_print(_atop_print, net):
    def net(self, pm):
        self.p_stdscr.addstr ('NET | tcpi %6dM | tcpo %7dM | udpi %6dM | udpo %7dM\n' % (
            self.get_metric_value('network.tcp.insegs'),
            self.get_metric_value('network.tcp.outsegs'),
            self.get_metric_value('network.udp.indatagrams'),
            self.get_metric_value('network.udp.outdatagrams')
            )
                       )
        for k in xrange(len(self.metric_pmids)):
            try:
                (inst, iname) = pm.pmGetInDom(self.metric_descs[k])
                break
            except pmErr, e:
                iname = "X"
        net_metric = self.get_metric_value('network.interface.in.bytes')
        if type(net_metric) == type([]):
            for j in xrange(len(self.get_metric_value('network.interface.in.bytes'))):
                self.p_stdscr.addstr ('NET | %12s | pcki %6dM | pcko %7dM | si %8dM | so %9dM\n' % (
                    iname[j],
                    self.get_metric_value('network.interface.in.packets')[j],
                    self.get_metric_value('network.interface.out.packets')[j],
                    self.get_metric_value('network.interface.in.bytes')[j],
                    self.get_metric_value('network.interface.out.bytes')[j]
            )
                               )

# _proc_print --------------------------------------------------


class _proc_print(_atop_print, proc):
    def proc(self):
        for j in xrange(len(self.get_metric_value('proc.psinfo.pid'))):
            if j > 20:
                break

            self.p_stdscr.addstr ('%5d %5d %5d %5d %5d %15s\n' % (
                    self.get_metric_value('proc.psinfo.pid')[j],
                    self.get_metric_value('proc.schedstat.cpu_time')[j],
                    self.get_metric_value('proc.id.uid')[j],
                    self.get_metric_value('proc.psinfo.flags')[j],
                    self.get_metric_value('proc.psinfo.exit_signal')[j],
                    self.get_metric_value('proc.psinfo.cmd')[j]
                    )
                                  )


# _generic_print --------------------------------------------------


class _generic_print(_atop_print, subsys):
    True


# main ----------------------------------------------------------------------


def main (stdscr):
    n_samples = 0
    i = 1
    subsys = list()
    cpu = _cpu_print()
    cpu.set_stdscr(stdscr)
    mem = _memory_print()
    mem.set_stdscr(stdscr)
    disk = _disk_print()
    disk.set_stdscr(stdscr)
    net = _net_print()
    net.set_stdscr(stdscr)
    proc = _proc_print()
    proc.set_stdscr(stdscr)
    output_file = ""
    input_file = ""
    duration = 0
    interval_arg = 1
    duration_arg = 0

    ss = _generic_print()
    sort = ""

    subsys_options = {"d":"disk",
                 "c":"cpu",
                 "n":"net",
                 "s":"scheduling",
                 "v":"various",
                 "c":"command",
                 "y":"threads",
                 "u":"user total",
                 "p":"process total",
                 }

    sort_options = {"C": "cpu",
                    "M": "mem",
                    "D": "disk",
                    "N": "net",
                    "A": "auto"}

    class nextOption ( Exception ):
        True

    while i < len(sys.argv):
        try:
            if (sys.argv[i][:1] == "-"):
                for s in subsys_options:
                    if sys.argv[i][1:] == s:
                        subsys.add([s[1]])
                        raise nextOption
                for s in sort_options:
                    if sys.argv[i][1:] == s:
                        sort = s[1]
                        raise nextOption
                if (sys.argv[i] == "--help" or sys.argv[i] == "-h"):
                    usage()
                    sys.exit(1)
                else:
                    print sys.argv[0] + ": Unknown option ", sys.argv[i]
                    print "Try `" + sys.argv[0] + " --help' for more information."
                    sys.exit(1)
            else:
                interval_arg = int(sys.argv[i])
                i += 1
                if (i < len(sys.argv)):
                    n_samples = int(sys.argv[i])
            i += 1
        except nextOption:
            True

    if input_file == "":
        try:
            pm = pmContext()
        except pmErr, e:
            print "Cannot connect to pmcd on %s" % "localhost"
            sys.exit(1)
    else:
        # -f saves the metrics in a directory, so get the archive basename
        lol = []
        if not os.path.exists(input_file):
            print input_file, "does not exist"
            sys.exit(1)
        if not os.path.isdir(input_file) or not os.path.exists(input_file + "/pmcollectl.pcp"):
            print input_file, "is not a", me, "playback directory"
            sys.exit(1)
        for line in open(input_file + "/" + me + ".pcp"):
            lol.append(line[:-1].split())
        archive = input_file + "/" + lol[len(lol)-1][2]
        try:
            pm = pmContext(pmapi.PM_CONTEXT_ARCHIVE, archive)
        except pmErr, e:
            print "Cannot open PCP archive: %s" % archive
            sys.exit(1)

    if duration_arg != 0:
        (code, timeval, errmsg) = pm.pmParseInterval(duration_arg)
        if code < 0:
            print errmsg
            sys.exit(1)
        duration = timeval.tv_sec

    if len(subsys) == 0:
        # method "pointers"
        cpu.setup_metrics (pm)
        subsys.append ([cpu.prc, None])
        subsys.append ([cpu.cpu, None])
        subsys.append ([cpu.get_stats, pm])
        mem.setup_metrics (pm)
        subsys.append ([mem.mem, None])
        subsys.append ([mem.get_stats, pm])
        disk.setup_metrics (pm)
        subsys.append ([disk.disk, pm])
        subsys.append ([disk.get_stats, pm])
        net.setup_metrics (pm)
        subsys.append ([net.net, pm])
        subsys.append ([net.get_stats, pm])
        proc.setup_metrics (pm)
        subsys.append ([proc.proc, None])
        subsys.append ([proc.get_stats, pm])

    (code, delta, errmsg) = pm.pmParseInterval(str(interval_arg) + " seconds")

    if output_file != "":
        configuration = "log mandatory on every " + str(interval_arg) + " seconds { "
        for s in subsys:
            configuration += s.dump_metrics()
        configuration += "}"
        if duration == 0:
            if n_samples != 0:
                duration = n_samples * interval_arg
            else:
                duration = 10 * interval_arg
        record (pm, configuration, duration, output_file)
        record_add_creator (output_file)
        sys.exit(0)

    for s in subsys:
        try:
            s.setup_metrics(pm)
        except:
            if input_file != "":
                args = ""
                for i in sys.argv:
                    args = args + " " + i
                print "Argument mismatch between invocation arguments:\n" + args
                record_check_creator(input_file, "and arguments used to create the playback directory\n ")
                sys.exit(1)
        if (s[1] != None):
            s[0](s[1])

    host = pm.pmGetContextHostName()
    if host == "localhost":
        host = os.uname()[1]

    stdscr.move (0,0)
    stdscr.addstr ('ATOP - %s\t\t%s elapsed\n' % (time.strftime("%c"), datetime.timedelta(0, cpu.get_metric_value('kernel.all.uptime'))))

    n = 0
    print n_samples
    try:
        while (n < n_samples) or (n_samples == 0):
            pm.pmtimevalSleep(delta)
            stdscr.move (2,0)
            for s in subsys:
                try:
                    if (s[1] == None):
                        # indirect call via method "pointers"
                        s[0]()
                    else:
                        s[0](s[1])
                except curses.error:
                    pass
            stdscr.refresh()
            n += 1
    except KeyboardInterrupt:
        True
    stdscr.refresh()
    time.sleep(3)

if __name__ == '__main__':
    curses.wrapper(main)
