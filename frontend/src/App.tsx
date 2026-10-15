import { useState, type FormEvent } from "react"
import { Button } from "@/components/ui/button"

type Capsule = {
  dependencies: { package: string }[]
  risks: { package: string; certainty: string; evidence: string }[]
  usages: unknown[]
  verification: { status: string }
  limitations: string[]
}

export default function App() {
  const [path, setPath] = useState("")
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState("")
  const [capsule, setCapsule] = useState<Capsule | null>(null)

  async function scan(event: FormEvent) {
    event.preventDefault()
    setBusy(true); setError(""); setCapsule(null)
    try {
      const response = await fetch("/api/scan", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path }),
      })
      if (!response.ok) throw new Error(`Scan failed (${response.status}): ${await response.text()}`)
      setCapsule(await response.json())
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Scan failed")
    } finally { setBusy(false) }
  }

  return <main className="mx-auto max-w-3xl space-y-6 p-6 sm:p-12">
    <header>
      <p className="text-sm text-slate-500">Dependency resilience · Phase 1</p>
      <h1 className="mt-2 text-4xl font-bold">GemForge</h1>
      <p className="mt-3 text-slate-600">Inspect local dependency declarations and Python imports. Scanning reads files without running repository code.</p>
    </header>
    <form onSubmit={scan} className="space-y-3 rounded-xl border border-slate-200 bg-white p-5">
      <label htmlFor="repository" className="block font-medium">Local repository path</label>
      <input id="repository" required value={path} onChange={event => setPath(event.target.value)}
        placeholder="C:/path/to/LinkWatch" className="w-full rounded-md border border-slate-300 p-3" />
      <Button disabled={busy || !path.trim()} type="submit">{busy ? "Scanning…" : "Scan repository"}</Button>
    </form>
    {error && <p role="alert" className="rounded-md border border-red-300 bg-red-50 p-4">{error}</p>}
    {capsule && <section aria-live="polite" className="space-y-4">
      <h2 className="text-xl font-semibold">Scan results</h2>
      <p>{capsule.dependencies.length} declarations · {capsule.usages.length} usage locations · Verification: {capsule.verification.status}</p>
      {capsule.risks.length ? <ul className="space-y-3">{capsule.risks.map((risk, index) =>
        <li key={index} className="rounded-md border border-amber-300 bg-amber-50 p-4">
          <strong>{risk.package}</strong> · {risk.certainty}<p>{risk.evidence}</p>
        </li>)}</ul> : <p>No risks detected by the implemented checks. This does not establish safety.</p>}
      <details><summary className="cursor-pointer font-medium">Analysis limitations</summary>
        <ul className="mt-3 list-disc space-y-2 pl-5">{capsule.limitations.map(item => <li key={item}>{item}</li>)}</ul>
      </details>
    </section>}
    <p className="text-sm text-slate-500">Gemma recommendations and original-vs-candidate verification are planned for Phase 2.</p>
  </main>
}
