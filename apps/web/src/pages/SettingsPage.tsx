import { TelegramCard } from '../features/settings/TelegramCard.tsx'

export default function SettingsPage() {
  return (
    <div className="mx-auto flex max-w-[720px] flex-col gap-6 px-4 pt-6 pb-24 md:px-10 md:pt-8">
      <h1 className="text-[26px]">설정</h1>
      <TelegramCard />
    </div>
  )
}
