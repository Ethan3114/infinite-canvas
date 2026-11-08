"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { ApiError, api } from "@/lib/api";

type Item = { id: string; elder_name: string; hometown: string };

export default function ProfilesPage() {
  const [items, setItems] = useState<Item[]>([]);
  const [name, setName] = useState("");
  const [hometown, setHometown] = useState("");
  const [familyNames, setFamilyNames] = useState("");
  const [topicsWant, setTopicsWant] = useState("");
  const [topicsAvoid, setTopicsAvoid] = useState("");
  const [message, setMessage] = useState("");

  async function load() {
    const data = await api<{ items: Item[] }>("/api/v1/profiles");
    setItems(data.items);
  }

  useEffect(() => {
    load().catch((error: unknown) => {
      setMessage(error instanceof ApiError ? error.message : "没有载入档案");
    });
  }, []);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setMessage("");
    try {
      await api("/api/v1/profiles", {
        method: "POST",
        body: JSON.stringify({
          elder_name: name,
          hometown,
          family_names: familyNames,
          topics_want: topicsWant,
          topics_avoid: topicsAvoid,
        }),
      });
      setName("");
      await load();
    } catch (error) {
      setMessage(error instanceof ApiError ? error.message : "没有保存");
    }
  }

  return (
    <main className="mx-auto max-w-2xl px-6 py-10">
      <p className="text-sm tracking-[0.2em] text-clay">家属</p>
      <h1 className="mt-2 text-4xl">给老人建一份档</h1>
      <form onSubmit={onSubmit} className="mt-8 space-y-3 rounded-3xl bg-white p-6">
        <input className="w-full rounded-2xl border border-ink/10 px-4 py-3 text-lg" placeholder="怎么称呼" value={name} onChange={(event) => setName(event.target.value)} />
        <input className="w-full rounded-2xl border border-ink/10 px-4 py-3 text-lg" placeholder="籍贯，可以不填" value={hometown} onChange={(event) => setHometown(event.target.value)} />
        <input className="w-full rounded-2xl border border-ink/10 px-4 py-3 text-lg" placeholder="家里人的名字" value={familyNames} onChange={(event) => setFamilyNames(event.target.value)} />
        <textarea className="w-full rounded-2xl border border-ink/10 px-4 py-3 text-lg" placeholder="想聊的事" value={topicsWant} onChange={(event) => setTopicsWant(event.target.value)} />
        <textarea className="w-full rounded-2xl border border-ink/10 px-4 py-3 text-lg" placeholder="不想聊的事" value={topicsAvoid} onChange={(event) => setTopicsAvoid(event.target.value)} />
        <button className="rounded-full bg-ink px-6 py-3 text-paper" type="submit">保存</button>
      </form>
      {message ? <p className="mt-4 text-clay">{message}</p> : null}
      <ul className="mt-8 space-y-3">
        {items.map((item) => (
          <li key={item.id}>
            <Link className="block rounded-3xl bg-white px-5 py-4 text-2xl" href={`/profiles/${item.id}`}>{item.elder_name}</Link>
          </li>
        ))}
      </ul>
    </main>
  );
}
