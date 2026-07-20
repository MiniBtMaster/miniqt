import { Suspense } from "react";
import { AppShell } from "@/components/AppShell";
import { AuthGate } from "@/components/AuthGate";

// 嵌入模式下（miniqt 内嵌），跳过 Maddie 登录认证
const IS_EMBEDDED = process.env.NEXT_PUBLIC_EMBEDDED === "true";

export default function Home() {
  return (
    <Suspense>
      {IS_EMBEDDED ? (
        <AppShell />
      ) : (
        <AuthGate>
          <AppShell />
        </AuthGate>
      )}
    </Suspense>
  );
}
