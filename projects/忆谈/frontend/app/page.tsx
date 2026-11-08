"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { ApiError, api } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [code, setCode] = useState("");
  const [message, setMessage] = useState("");

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setMessage("");
    try {
      await api("/api/v1/auth/login", { method: "POST", body: JSON.stringify({ code }) });
      router.push("/profiles");
    } catch (error) {
      setMessage(error instanceof ApiError ? error.message : "登录没有完成");
    }
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-md flex-col justify-center px-6">
      <p className="text-sm tracking-[0.2em] text-clay">忆谈</p>
      <h1 className="mt-3 text-4xl leading-tight">先用邀请码进来</h1>
      <p className="mt-4 text-lg leading-relaxed text-ink/70">这是给一位老人建档、开口聊天的地方。邀请码写在你电脑的 backend/.env 里，不要发到对话中。</p>
      <form onSubmit={onSubmit} className="mt-8 space-y-4">
        <input
          value={code}
          onChange={(event) => setCode(event.target.value)}
          className="w-full rounded-2xl border border-ink/10 bg-white px-4 py-4 text-xl outline-none"
          placeholder="邀请码"
          autoComplete="off"
        />
        <button className="w-full rounded-full bg-ink py-4 text-lg text-paper" type="submit">进入</button>
      </form>
      {message ? <p className="mt-4 text-clay">{message}</p> : null}
    </main>
  );
}
