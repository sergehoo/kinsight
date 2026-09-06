import { Brand } from "./Brand";
import { HeaderActions } from "./HeaderActions";
import { TopNav } from "./TopNav";

/** En-tête commun : logo, navigation centrale, actions à droite. */
export function AppHeader() {
  return (
    <header className="relative z-30 flex flex-wrap items-center justify-between gap-3 px-4 py-4 sm:gap-5 sm:px-8 sm:py-6 lg:flex-nowrap lg:px-12 lg:py-8">
      <div className="shrink-0">
        <Brand />
      </div>
      {/* Le nav occupe l'espace RESTANT et défile chez lui : il ne peut plus
          passer sous les actions (l'ancien `absolute` les recouvrait). */}
      <div className="order-3 flex w-full min-w-0 justify-center overflow-x-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden lg:order-none lg:w-auto lg:flex-1">
        <TopNav />
      </div>
      <div className="shrink-0">
        <HeaderActions />
      </div>
    </header>
  );
}
