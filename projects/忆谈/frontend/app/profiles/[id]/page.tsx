"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { API_BASE, ApiError, api, apiForm } from "@/lib/api";
import { CallPanel } from "@/components/call-panel";

type Paragraph = { id: string; text: string; source_quote: string };
type Chapter = {
  id: string;
  title: string;
  paragraphs: Paragraph[];
  facts: { id: string; topic: string; detail: string; status: string }[];
  memories: { kind: string; name: string; detail: string }[];
};
type CallItem = {
  id: string;
  status: string;
  failure_code: string;
  texts: Record<string, string>;
  chapter: Chapter | null;
  chapters?: Chapter[];
};
type Profile = {
  id: string;
  elder_name: string;
  hometown: string;
  calls: CallItem[];
};

function elderWords(call: CallItem) {
  return (call.texts.full || call.texts.side || call.texts.realtime_user || "").trim();
}

function isFinished(call: CallItem) {
  return call.status === "ready" || call.status === "failed";
}

function callHasWords(call: CallItem) {
  return Boolean(elderWords(call) || (call.texts.realtime_assistant || "").trim());
}

function writtenChapters(call: CallItem) {
  const listed = (call.chapters ?? []).filter((chapter) => chapter.paragraphs.length > 0);
  if (listed.length > 0) return listed;
  if (call.chapter && call.chapter.paragraphs.length > 0) return [call.chapter];
  return [];
}

export default function ProfilePage({ params }: { params: { id: string } }) {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [voiceReady, setVoiceReady] = useState(false);
  const [message, setMessage] = useState("");
  const [openQuote, setOpenQuote] = useState("");
  const [writingReady, setWritingReady] = useState(false);
  const [writingCall, setWritingCall] = useState("");

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      api<{ voice_ready: boolean; writing_ready: boolean }>("/api/v1/me"),
      api<Profile>(`/api/v1/profiles/${params.id}`),
    ])
      .then(([me, detail]) => {
        if (cancelled) return;
        setVoiceReady(me.voice_ready);
        setWritingReady(me.writing_ready);
        setProfile(detail);
      })
      .catch((error: unknown) => {
        if (!cancelled) setMessage(error instanceof ApiError ? error.message : "没有打开档案");
      });
    return () => {
      cancelled = true;
    };
  }, [params.id]);

  async function onPhoto(file: File | undefined) {
    if (!file || !profile) return;
    const body = new FormData();
    body.append("file", file);
    try {
      await apiForm(`/api/v1/profiles/${profile.id}/photos`, body);
      setMessage("照片已留下");
    } catch (error) {
      setMessage(error instanceof ApiError ? error.message : "照片没有保存");
    }
  }

  async function setFact(factId: string, status: string) {
    try {
      await api(`/api/v1/facts/${factId}`, { method: "POST", body: JSON.stringify({ status }) });
      window.location.reload();
    } catch (error) {
      setMessage(error instanceof ApiError ? error.message : "这条核对没有记下");
    }
  }

  async function makeChapter(callId: string) {
    setMessage("");
    setWritingCall(callId);
    try {
      await api(`/api/v1/calls/${callId}/draft`, { method: "POST" });
      window.location.reload();
    } catch (error) {
      setWritingCall("");
      setMessage(error instanceof ApiError ? error.message : "没有整理出来");
    }
  }

  if (!profile) {
    return <main className="mx-auto max-w-2xl px-6 py-10">{message || "正在打开"}</main>;
  }

  const written = profile.calls.filter((call) => writtenChapters(call).length > 0);
  const waiting = profile.calls.filter((call) => isFinished(call) && writtenChapters(call).length === 0);
  const unfinished = profile.calls.some((call) => !isFinished(call) && writtenChapters(call).length === 0);

  return (
    <main className="mx-auto max-w-2xl px-6 py-10">
      <Link className="text-sm text-clay" href="/profiles">返回档案</Link>
      <h1 className="mt-6 text-4xl">{profile.elder_name}</h1>
      <p className="mt-2 text-lg text-ink/70">{profile.hometown || "还没有写籍贯"}</p>

      <section className="mt-8">
        <h2 className="text-sm tracking-[0.2em] text-clay">这一次</h2>
        {written.length > 0 ? <p className="mt-3 text-sm text-ink/60">开场会提起最近写成的那一章。</p> : null}
        <div className="mt-3">
          <CallPanel profileId={profile.id} voiceReady={voiceReady} onFinished={() => { window.location.reload(); }} />
        </div>
        {message ? <p className="mt-4 text-clay">{message}</p> : null}
      </section>

      {written.length > 0 ? (
        <section className="mt-12">
          <h2 className="text-sm tracking-[0.2em] text-clay">已经写成的</h2>
          <div className="mt-4 space-y-8">
            {written.map((call) => (
              <article key={call.id}>
                {writtenChapters(call).map((chapter) => (
                  <div key={chapter.id} className="mt-8 first:mt-0">
                    <h3 className="text-3xl leading-snug">{chapter.title}</h3>
                    <div className="mt-5 space-y-5 text-lg leading-8">
                      {chapter.paragraphs.map((paragraph) => (
                        <div key={paragraph.id}>
                          <p>{paragraph.text}</p>
                          <button className="mt-1 text-sm text-clay" type="button" onClick={() => setOpenQuote(openQuote === paragraph.id ? "" : paragraph.id)}>
                            {openQuote === paragraph.id ? "收起" : "这句原话"}
                          </button>
                          {openQuote === paragraph.id ? <p className="mt-1 text-base leading-7 text-ink/60">{paragraph.source_quote}</p> : null}
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
                {writtenChapters(call).some((chapter) => chapter.facts.some((fact) => fact.detail)) ? (
                  <details className="mt-6 text-sm leading-6 text-ink/60">
                    <summary className="cursor-pointer">先不写进正文的</summary>
                    <ul className="mt-3 space-y-3">
                      {writtenChapters(call).flatMap((chapter) => chapter.facts).filter((fact) => fact.detail).map((fact) => (
                        <li key={fact.id}>
                          <p>{fact.detail}</p>
                          {fact.status === "confirmed" ? <p>已确认</p> : null}
                          {fact.status === "rejected" ? <p>已拿掉</p> : null}
                          {fact.status === "open" ? (
                            <p className="mt-1">
                              <button type="button" onClick={() => setFact(fact.id, "confirmed")}>确认</button>
                              <button className="ml-4" type="button" onClick={() => setFact(fact.id, "rejected")}>这句不要</button>
                            </p>
                          ) : null}
                        </li>
                      ))}
                    </ul>
                  </details>
                ) : null}
                <details className="mt-4 text-sm leading-6 text-ink/60">
                  <summary className="cursor-pointer">录音和原话</summary>
                  <audio className="mt-3 w-full" controls crossOrigin="use-credentials" src={`${API_BASE}/api/v1/calls/${call.id}/audio/user`} />
                  {elderWords(call) ? <p className="mt-3 whitespace-pre-wrap">{elderWords(call)}</p> : null}
                  {writingReady ? (
                    <button className="mt-3 text-clay" type="button" disabled={writingCall === call.id} onClick={() => makeChapter(call.id)}>
                      {writingCall === call.id ? "正在写" : "按原话再写一遍"}
                    </button>
                  ) : null}
                </details>
              </article>
            ))}
          </div>
        </section>
      ) : null}

      {waiting.length > 0 ? (
        <section className="mt-12">
          <h2 className="text-sm tracking-[0.2em] text-clay">还没写成</h2>
          <div className="mt-4 space-y-4">
            {waiting.map((call) => (
              <article key={call.id} className="rounded-3xl bg-white px-6 py-6">
                <p className="text-lg">{callHasWords(call) ? "这通已经说完。" : "这通中断了，声音留下了，字没有转出来。"}</p>
                <audio className="mt-3 w-full" controls crossOrigin="use-credentials" src={`${API_BASE}/api/v1/calls/${call.id}/audio/user`} />
                {callHasWords(call) ? (
                  <button
                    className="mt-4 rounded-full bg-ink px-5 py-3 text-paper disabled:opacity-50"
                    type="button"
                    disabled={writingCall === call.id}
                    onClick={() => makeChapter(call.id)}
                  >
                    {writingCall === call.id ? "正在写成一段回忆" : writingReady ? "写成一段回忆" : "写成一段回忆（还缺写作用的钥匙）"}
                  </button>
                ) : null}
              </article>
            ))}
          </div>
        </section>
      ) : null}

      {unfinished ? <p className="mt-8 text-sm text-ink/50">还有一通没说完。</p> : null}

      <details className="mt-12 text-sm text-ink/60">
        <summary className="cursor-pointer">放一张老照片</summary>
        <input className="mt-3 block w-full" type="file" accept="image/jpeg,image/png,image/webp" onChange={(event) => onPhoto(event.target.files?.[0])} />
      </details>
    </main>
  );
}
