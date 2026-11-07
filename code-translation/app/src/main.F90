! main.F90 -- rd2d: Gray-Scott reaction-diffusion on a 2-D mesh; parameters from input.nml.
program rd2d
   use config, only: config_t, read_config
   implicit none
   type(config_t) :: cfg

   call read_config(cfg, "input.nml")
   call run_simulation(cfg)
end program rd2d
