import LogoutButton from "@/components/logout-button";

const Page = () => {
  return (
    <div className="flex h-full w-full flex-col items-center justify-center gap-4">
      <h1 className="text-2xl font-bold">Spark</h1>
      <LogoutButton />
    </div>
  );
};

export default Page;
