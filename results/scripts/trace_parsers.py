#!/usr/bin/env python3
"""Shared trace parsers for static and interactive plots."""

from collections import defaultdict
import csv
import struct

import numpy as np


def parse_cwnd_ack(cwnd_file, read_stride=1):
    """Parse CWND trace into ACK analysis fields keyed by (src, dport).

    Returns:
        dict[(src, dport)] -> {"t": [s], "seq": [int], "rtt": [us|None]}
    """
    flows = defaultdict(lambda: {"t": [], "seq": [], "rtt": []})
    read_stride = max(1, int(read_stride))

    is_binary = cwnd_file.endswith('.tr')
    if is_binary:
        try:
            dtype = np.dtype([
                ("time", "<u8"),
                ("sip", "<u4"),
                ("dip", "<u4"),
                ("sport", "<u4"),
                ("dport", "<u4"),
                ("rate", "<u8"),
                ("win", "<u8"),
                ("lastRtt", "<u8"),
                ("lastAckSeq", "<u4"),
                ("_pad", "<u4"),
            ])
            with open(cwnd_file, 'rb') as f:
                raw = f.read()
            if len(raw) < dtype.itemsize:
                return flows

            arr = np.frombuffer(raw, dtype=dtype)
            if read_stride > 1:
                arr = arr[::read_stride]
            if arr.size == 0:
                return flows

            key_a = (arr["sip"].astype(np.uint64) << 32) | arr["dport"].astype(np.uint64)
            sort_idx = np.argsort(key_a, kind="mergesort")
            arr = arr[sort_idx]
            key_a = key_a[sort_idx]
            boundaries = np.where(np.diff(key_a) != 0)[0] + 1
            chunks = np.split(arr, boundaries)

            for chunk in chunks:
                key = (int(chunk["sip"][0]), int(chunk["dport"][0]))
                flows[key]["t"] = (chunk["time"] / 1e9).tolist()
                flows[key]["seq"] = chunk["lastAckSeq"].astype(np.uint64).tolist()
                rtt_raw = chunk["lastRtt"].astype(np.uint64)
                flows[key]["rtt"] = [
                    (v / 1000.0) if v < 100000000 else None
                    for v in rtt_raw
                ]
            return flows
        except Exception:
            is_binary = False

    if not is_binary:
        with open(cwnd_file, 'r') as f:
            rec_idx = 0
            for line in f:
                rec_idx += 1
                if (rec_idx % read_stride) != 0:
                    continue
                parts = line.strip().split()
                if len(parts) < 9:
                    continue
                try:
                    t_ns = int(parts[0])
                    src = int(parts[1])
                    dport = int(parts[4])
                    last_rtt = int(parts[7])
                    last_ack_seq = int(parts[8])
                except (ValueError, IndexError):
                    continue
                key = (src, dport)
                flows[key]["t"].append(t_ns / 1e9)
                flows[key]["seq"].append(last_ack_seq)
                flows[key]["rtt"].append((last_rtt / 1000.0) if last_rtt < 100000000 else None)

    return flows


def parse_rxbuf_series(rxbuf_path):
    """Parse RX buffer trace and return series keyed by (node, intf)."""
    data = defaultdict(lambda: {"t": [], "bytes": []})

    is_binary = rxbuf_path.endswith('.tr')
    if not is_binary:
        try:
            with open(rxbuf_path, 'rb') as f:
                header = f.read(8)
                if len(header) == 8 and any(b == 0 for b in header):
                    is_binary = True
        except Exception:
            pass

    if is_binary:
        try:
            dtype = np.dtype([
                ("time", "<u8"),
                ("node", "<u4"),
                ("intf", "<u4"),
                ("bytes", "<u8"),
            ])
            with open(rxbuf_path, 'rb') as f:
                raw = f.read()
            if len(raw) >= dtype.itemsize:
                arr = np.frombuffer(raw, dtype=dtype)
                keys = np.stack([arr["node"], arr["intf"]], axis=1)
                uniq = np.unique(keys, axis=0)
                for node, intf in uniq:
                    mask = (arr["node"] == node) & (arr["intf"] == intf)
                    series = arr[mask]
                    key = (int(node), int(intf))
                    data[key]["t"] = (series["time"] / 1e9).tolist()
                    data[key]["bytes"] = series["bytes"].astype(np.uint64).tolist()
                return data
        except Exception:
            is_binary = False

    if not is_binary:
        with open(rxbuf_path, 'r') as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) < 4:
                    continue
                try:
                    t_ns = int(parts[0])
                    node = int(parts[1])
                    intf = int(parts[2])
                    b = int(parts[3])
                except ValueError:
                    continue
                key = (node, intf)
                data[key]["t"].append(t_ns / 1e9)
                data[key]["bytes"].append(b)

    return data


def parse_queue_depth_binned(csv_path, allowed_hops=None, bin_s=0.001, collect_all_qlens=False, max_sim_time_s=600.0):
    """Parse queue depth trace/csv into per-bin max queue depth.

    Returns:
      max_bins: dict[bin_idx] -> max_qlen
      all_qlens: list[int] (possibly empty)
    """
    raw = defaultdict(int)
    all_qlens = []

    is_binary = csv_path.endswith('.tr')
    if is_binary:
        try:
            fmt = "<QIII4x"
            sz = struct.calcsize(fmt)
            max_bin = int(max_sim_time_s / bin_s)
            with open(csv_path, 'rb') as f:
                while True:
                    data = f.read(sz)
                    if not data or len(data) < sz:
                        break
                    t_ns, qp_id, hop, qlen = struct.unpack(fmt, data)[:4]
                    if allowed_hops is not None and hop not in allowed_hops:
                        continue
                    b = int((t_ns / 1e9) / bin_s)
                    if b < 0 or b > max_bin:
                        continue
                    if qlen > raw[b]:
                        raw[b] = qlen
                    if collect_all_qlens:
                        all_qlens.append(qlen)
            return raw, all_qlens
        except Exception:
            is_binary = False

    if not is_binary:
        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    hop = int(row['Hop'])
                    if allowed_hops is not None and hop not in allowed_hops:
                        continue
                    t = float(row['Time'])
                    qlen = int(row['Qlen'])
                except (KeyError, ValueError):
                    continue
                b = int(t / bin_s)
                if qlen > raw[b]:
                    raw[b] = qlen
                if collect_all_qlens:
                    all_qlens.append(qlen)

    return raw, all_qlens
