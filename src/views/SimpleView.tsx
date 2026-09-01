import { Panel } from '../components/Panel';
export function SimpleView({ title, description }: { title: string; description: string }) { return <Panel title={title}><div className="p-6 text-sm text-[#8B949E]">{description}</div></Panel>; }
