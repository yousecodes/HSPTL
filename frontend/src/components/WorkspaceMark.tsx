import type { SVGProps } from 'react';
export type WorkspaceMarkName = 'board' | 'clinic' | 'rounds' | 'lab' | 'exam' | 'oncall' | 'conference' | 'tools';
const palette: Record<WorkspaceMarkName, string> = { board:'#0F766E', clinic:'#16805D', rounds:'#5267A8', lab:'#0D8B91', exam:'#B77924', oncall:'#C65B50', conference:'#64748B', tools:'#66736B' };
export function WorkspaceMark({name,size=24,className='',...props}:{name:WorkspaceMarkName;size?:number;className?:string}&SVGProps<SVGSVGElement>){
 const c=palette[name];
 const common={fill:c};
 return <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true" className={className} {...props}>
 {name==='board' && <><rect x="4" y="5" width="24" height="22" rx="5" {...common}/><path d="M9 11h14M9 16h8M9 21h11" stroke="white" strokeWidth="2" strokeLinecap="round"/></>}
 {name==='clinic' && <><path d="M10 4h4v5h4V4h4v7a7 7 0 0 1-14 0V4h2Z" {...common}/><path d="M16 18v7a3 3 0 0 0 6 0v-2" stroke={c} strokeWidth="3" fill="none" strokeLinecap="round"/><circle cx="22" cy="21" r="3" {...common}/></>}
 {name==='rounds' && <><circle cx="16" cy="9" r="5" {...common}/><circle cx="7" cy="13" r="3.5" {...common}/><circle cx="25" cy="13" r="3.5" {...common}/><path d="M7 27c0-6 3-9 9-9s9 3 9 9H7Z" {...common}/></>}
 {name==='lab' && <><path d="M12 4h8v3l-2 2v5l8 11a2 2 0 0 1-2 3H8a2 2 0 0 1-2-3l8-11V9l-2-2V4Z" {...common}/><path d="M10 22h12" stroke="white" strokeWidth="2" strokeLinecap="round"/></>}
 {name==='exam' && <><rect x="6" y="5" width="20" height="24" rx="3" {...common}/><rect x="11" y="3" width="10" height="5" rx="2" fill={c}/><path d="m10 15 2 2 4-4m-6 10h9" stroke="white" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round"/></>}
 {name==='oncall' && <><path d="M17 3 7 18h7l-1 11 12-17h-8l2-9Z" {...common}/></>}
 {name==='conference' && <><circle cx="16" cy="8" r="4" {...common}/><circle cx="6" cy="13" r="3" {...common}/><circle cx="26" cy="13" r="3" {...common}/><path d="M9 27c0-6 2-10 7-10s7 4 7 10H9Zm-8 0c0-5 1-8 5-9l3 2-1 7H1Zm21 0-1-7 3-2c4 1 5 4 5 9h-7Z" {...common}/></>}
 {name==='tools' && <><path d="M19 4a7 7 0 0 0-8 9L4 20a4 4 0 1 0 6 6l7-7a7 7 0 0 0 9-8l-4 4-5-1-1-5 3-5Z" {...common}/></>}
 </svg>
}
