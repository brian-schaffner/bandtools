import { Suspense } from "react";
import { SigninView } from "@/components/signin-view";

export const metadata = { title: "Sign in · Gig Flyer Studio" };

export default function SigninPage() {
  return (
    <Suspense fallback={null}>
      <SigninView />
    </Suspense>
  );
}
