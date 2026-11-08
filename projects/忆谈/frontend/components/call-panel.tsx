"use client";

import { useEffect, useRef, useState } from "react";
import { ApiError, api, wsUrl } from "@/lib/api";
import { canStartCall } from "@/lib/call-gate";

type Props = { profileId: string; voiceReady: boolean; onFinished: () => void };

function toPcm16k(input: Float32Array, inputRate: number): Int16Array {
  const ratio = inputRate / 16000;
  const length = Math.max(0, Math.floor(input.length / ratio));
  const out = new Int16Array(length);
  for (let index = 0; index < length; index += 1) {
    const sample = Math.max(-1, Math.min(1, input[Math.floor(index * ratio)] || 0));
    out[index] = sample < 0 ? sample * 0x8000 : sample * 0x7fff;
  }
  return out;
}

export function CallPanel({ profileId, voiceReady, onFinished }: Props) {
  const [consent, setConsent] = useState(false);
  const [live, setLive] = useState(false);
  const [message, setMessage] = useState("");
  const socketRef = useRef<WebSocket | null>(null);
  const audioRef = useRef<AudioContext | null>(null);
  const playAt = useRef(0);
  const pending = useRef<number[]>([]);

  useEffect(() => () => { socketRef.current?.close(); void audioRef.current?.close(); }, []);

  function playChunk(pcm: string) {
    const context = audioRef.current;
    if (!context) return;
    const binary = atob(pcm);
    const bytes = new Uint8Array(binary.length);
    for (let index = 0; index < binary.length; index += 1) bytes[index] = binary.charCodeAt(index);
    const view = new DataView(bytes.buffer);
    const samples = new Float32Array(Math.floor(bytes.length / 2));
    for (let index = 0; index < samples.length; index += 1) samples[index] = view.getInt16(index * 2, true) / 32768;
    const buffer = context.createBuffer(1, samples.length, 24000);
    buffer.copyToChannel(samples, 0);
    const source = context.createBufferSource();
    source.buffer = buffer;
    source.connect(context.destination);
    const start = Math.max(context.currentTime + 0.05, playAt.current);
    source.start(start);
    playAt.current = start + buffer.duration;
  }

  async function start() {
    setMessage("");
    if (!consent) {
      setMessage("请先勾选老人同意录音");
      return;
    }
    if (!canStartCall(true, voiceReady)) {
      setMessage("还没有配置豆包语音钥匙，通话暂时不能开始");
      return;
    }
    try {
      const opened = await api<{ id: string }>("/api/v1/calls", {
        method: "POST",
        body: JSON.stringify({ profile_id: profileId, consent: true }),
      });
      const context = new AudioContext();
      audioRef.current = context;
      playAt.current = context.currentTime;
      await context.audioWorklet.addModule("/pcm-worklet.js");
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, channelCount: 1 },
      });
      const source = context.createMediaStreamSource(stream);
      const node = new AudioWorkletNode(context, "pcm-capture");
      source.connect(node);
      const socket = new WebSocket(wsUrl(opened.id));
      socketRef.current = socket;
      node.port.onmessage = (event: MessageEvent<Float32Array>) => {
        if (socket.readyState !== WebSocket.OPEN) return;
        const pcm = toPcm16k(event.data, context.sampleRate);
        pending.current.push(...pcm);
        while (pending.current.length >= 320) {
          const slice = pending.current.slice(0, 320);
          pending.current = pending.current.slice(320);
          const bytes = new Uint8Array(slice.length * 2);
          const view = new DataView(bytes.buffer);
          slice.forEach((sample, index) => view.setInt16(index * 2, sample, true));
          let text = "";
          bytes.forEach((value) => { text += String.fromCharCode(value); });
          socket.send(JSON.stringify({ type: "audio", pcm: btoa(text) }));
        }
      };
      socket.onmessage = (event) => {
        const payload = JSON.parse(event.data as string) as { type: string; text?: string; pcm?: string; error?: { message: string } };
        if (payload.type === "ready") setLive(true);
        if (payload.type === "audio" && payload.pcm) playChunk(payload.pcm);
        if (payload.type === "done") { setLive(false); onFinished(); }
        if (payload.type === "error") { setLive(false); setMessage(payload.error?.message || "通话没有完成"); onFinished(); }
      };
    } catch (error) {
      setMessage(error instanceof ApiError ? error.message : "通话没有开始");
    }
  }

  function stop() {
    socketRef.current?.send(JSON.stringify({ type: "stop" }));
    setLive(false);
  }

  return (
    <section className="rounded-3xl bg-white p-6">
      <label className="flex items-start gap-3 text-lg">
        <input type="checkbox" className="mt-2 h-5 w-5" checked={consent} onChange={(event) => setConsent(event.target.checked)} />
        <span>老人本人同意录音。不同意就不会开始，也不会留下声音。</span>
      </label>
      <button
        className="mt-6 w-full rounded-full bg-ink py-6 text-2xl text-paper disabled:opacity-40"
        type="button"
        onClick={live ? stop : start}
      >
        {live ? "结束通话" : "开始通话"}
      </button>
      {message ? <p className="mt-4 text-clay">{message}</p> : null}
      {live ? <p className="mt-6 text-lg text-ink/70">正在聊。说完点结束。</p> : null}
    </section>
  );
}
