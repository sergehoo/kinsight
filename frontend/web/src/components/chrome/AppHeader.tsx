import { Brand } from "./Brand";
import { HeaderActions } from "./HeaderActions";
import { TopNav } from "./TopNav";

/** En-tête commun : logo, navigation centrale, actions à droite. */
export function AppHeader() {
  return (
    <header className="relative z-30 flex flex-wrap items-center justify-between gap-5 px-8 py-8 sm:px-10 lg:px-12">
      <Brand />
      <div className="order-3 w-full justify-center lg:order-none lg:absolute lg:left-1/2 lg:top-9 lg:flex lg:w-auto lg:-translate-x-1/2">
        <TopNav />
      </div>
      <HeaderActions />
    </header>
  );
}
