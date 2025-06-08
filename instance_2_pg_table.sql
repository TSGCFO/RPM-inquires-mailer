-- Table: public.quote_requests

-- DROP TABLE IF EXISTS public.quote_requests;

CREATE TABLE IF NOT EXISTS public.quote_requests
(
    id integer NOT NULL DEFAULT nextval('quote_requests_id_seq'::regclass),
    name text COLLATE pg_catalog."default" NOT NULL,
    email text COLLATE pg_catalog."default" NOT NULL,
    phone text COLLATE pg_catalog."default" NOT NULL,
    company text COLLATE pg_catalog."default" NOT NULL,
    service text COLLATE pg_catalog."default" NOT NULL,
    message text COLLATE pg_catalog."default",
    consent boolean NOT NULL,
    created_at timestamp without time zone NOT NULL DEFAULT now(),
    status text COLLATE pg_catalog."default" NOT NULL DEFAULT 'new'::text,
    assigned_to integer,
    converted_to_client boolean DEFAULT false,
    current_shipments text COLLATE pg_catalog."default",
    expected_shipments text COLLATE pg_catalog."default",
    services text COLLATE pg_catalog."default",
    CONSTRAINT quote_requests_pkey PRIMARY KEY (id),
    CONSTRAINT quote_requests_assigned_to_users_id_fk FOREIGN KEY (assigned_to)
        REFERENCES public.users (id) MATCH SIMPLE
        ON UPDATE NO ACTION
        ON DELETE NO ACTION
)

TABLESPACE pg_default;

ALTER TABLE IF EXISTS public.quote_requests
    OWNER to rpm_auto_user;

/*
  NOTE: The trigger trg_notify_new_quote_request and its accompanying function
  are defined for database instance 2. The program's listener for DB 2
  watches the 'new_record_channel' notifications emitted by this trigger.
*/

-- Trigger: trg_notify_new_quote_request

-- DROP TRIGGER IF EXISTS trg_notify_new_quote_request ON public.quote_requests;

CREATE OR REPLACE TRIGGER trg_notify_new_quote_request
    AFTER INSERT
    ON public.quote_requests
    FOR EACH ROW
    EXECUTE FUNCTION public.notify_new_quote_request();













    -- FUNCTION: public.notify_new_quote_request()

-- DROP FUNCTION IF EXISTS public.notify_new_quote_request();

CREATE OR REPLACE FUNCTION public.notify_new_quote_request()
    RETURNS trigger
    LANGUAGE 'plpgsql'
    COST 100
    VOLATILE NOT LEAKPROOF SECURITY DEFINER
AS $BODY$

BEGIN

    PERFORM pg_notify(

        'new_record_channel',

        json_build_object('id', NEW.id)::text

    );

    RETURN NEW;

END;

$BODY$;

ALTER FUNCTION public.notify_new_quote_request()
    OWNER TO rpm_auto_user;
