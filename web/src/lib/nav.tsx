"use client";
/**
 * Routing for the Studio, backed by Next.js App Router.
 *
 * Exposes the small surface the components were written against (Link, NavLink,
 * useNavigate, useParams, useSearchParams, useLocation) so screens stay
 * framework-light. The implementation is swappable through NavImplContext:
 * Next.js in the app, an in-memory router in tests (src/test/testRouter.tsx).
 */
import NextLink from "next/link";
import {
  useParams as useNextParams,
  usePathname,
  useRouter,
  useSearchParams as useNextSearchParams,
} from "next/navigation";
import {
  createContext,
  forwardRef,
  useCallback,
  useContext,
  useMemo,
  useLayoutEffect,
  useRef,
  type AnchorHTMLAttributes,
  type ReactNode,
} from "react";

export type NavigateOptions = { replace?: boolean };
export type NavigateFn = (to: string | number, opts?: NavigateOptions) => void;
type SearchInit = URLSearchParams | Record<string, string>;
type SetSearch = (
  next: SearchInit | ((prev: URLSearchParams) => SearchInit),
  opts?: NavigateOptions,
) => void;

export interface NavImpl {
  usePathname(): string;
  useSearch(): string;
  useParams(): Record<string, string>;
  useNavigate(): NavigateFn;
}

const nextImpl: NavImpl = {
  usePathname: () => usePathname() ?? "/",
  useSearch: () => useNextSearchParams()?.toString() ?? "",
  useParams: () => {
    const p = useNextParams() ?? {};
    const out: Record<string, string> = {};
    for (const [k, v] of Object.entries(p)) out[k] = Array.isArray(v) ? v.join("/") : String(v);
    return out;
  },
  useNavigate: () => {
    const router = useRouter();
    return useCallback<NavigateFn>((to, opts) => {
      if (typeof to === "number") {
        if (to < 0) router.back(); else router.forward();
        return;
      }
      if (opts?.replace) router.replace(to); else router.push(to);
    }, [router]);
  },
};

export const NavImplContext = createContext<NavImpl>(nextImpl);
const useImpl = () => useContext(NavImplContext);

export function useParams<T extends Record<string, string> = Record<string, string>>(): Partial<T> {
  return useImpl().useParams() as Partial<T>;
}

export function useNavigate(): NavigateFn {
  return useImpl().useNavigate();
}

export function useLocation(): { pathname: string; search: string } {
  const impl = useImpl();
  const pathname = impl.usePathname();
  const raw = impl.useSearch();
  return { pathname, search: raw ? `?${raw.replace(/^\?/, "")}` : "" };
}

export function useSearchParams(): [URLSearchParams, SetSearch] {
  const impl = useImpl();
  const pathname = impl.usePathname();
  const raw = impl.useSearch();
  const navigate = impl.useNavigate();
  const params = useMemo(() => new URLSearchParams(raw), [raw]);
  const latest = useRef(raw);
  useLayoutEffect(() => { latest.current = raw; }, [raw]);
  const set = useCallback<SetSearch>((next, opts) => {
    const resolved = typeof next === "function" ? next(new URLSearchParams(latest.current)) : next;
    const qs = new URLSearchParams(resolved as Record<string, string>).toString();
    if (qs === latest.current) return;
    navigate(qs ? `${pathname}?${qs}` : pathname, opts);
  }, [navigate, pathname]);
  return [params, set];
}

type LinkProps = Omit<AnchorHTMLAttributes<HTMLAnchorElement>, "href"> & {
  to: string;
  replace?: boolean;
  children?: ReactNode;
};

export const Link = forwardRef<HTMLAnchorElement, LinkProps>(function Link(
  { to, replace, ...rest }, ref,
) {
  return <NextLink ref={ref} href={to} replace={replace} {...rest} />;
});

type NavLinkProps = Omit<LinkProps, "className"> & {
  end?: boolean;
  className?: string | ((s: { isActive: boolean }) => string);
};

export function NavLink({ to, end, className, ...rest }: NavLinkProps) {
  const pathname = useImpl().usePathname();
  const isActive = end ? pathname === to : pathname === to || pathname.startsWith(to.endsWith("/") ? to : `${to}/`);
  const cls = typeof className === "function" ? className({ isActive }) : className;
  return <Link to={to} className={cls} aria-current={isActive ? "page" : undefined} {...rest} />;
}
